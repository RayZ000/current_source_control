"""High-level Keithley 2612 controller built on top of a transport layer."""
from __future__ import annotations

import time

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Optional

from .transport import InstrumentTransport




@dataclass
class ErrorEntry:
    code: int
    message: str
    severity: int
    node: int

class Channel(str, Enum):
    """SMU channel identifiers."""

    A = "smua"
    B = "smub"

    @property
    def alias(self) -> str:
        return str(self.value)


@dataclass
class VoltageConfig:
    level_v: float
    current_limit_a: float
    autorange: bool = True


class Keithley2612Controller:
    """Thin wrapper enforcing safe command sequences for the 2612."""

    def __init__(self, transport: InstrumentTransport, *, default_channel: Channel = Channel.A) -> None:
        self._transport = transport
        self._channel = default_channel
        self._connected = False

    @property
    def channel(self) -> Channel:
        return self._channel

    def connect(self) -> None:
        if self._connected:
            return
        self._transport.open()
        self._connected = True

    def disconnect(self) -> None:
        if not self._connected:
            return
        self._transport.close()
        self._connected = False

    def identify(self) -> str:
        return self._transport.query("*IDN?")

    def reset(self) -> None:
        self._write("*RST")
        self._write(f"{self._channel.alias}.reset()")

    def select_channel(self, channel: Channel) -> None:
        if channel == self._channel:
            return
        self._channel = channel
        # Reset the new channel to a known state before use.
        self._write(f"{channel.alias}.reset()")

    def configure_voltage_source(self, config: VoltageConfig) -> None:
        alias = self._channel.alias
        commands: list[str] = [
            f"{alias}.source.func = {alias}.OUTPUT_DCVOLTS",
        ]
        if config.autorange:
            commands.append(f"{alias}.source.autorangev = {alias}.AUTORANGE_ON")
        else:
            commands.append(f"{alias}.source.autorangev = {alias}.AUTORANGE_OFF")
        commands.extend(
            [
                f"{alias}.source.levelv = {config.level_v}",
                f"{alias}.source.limiti = {config.current_limit_a}",
            ]
        )
        self._batch_write(commands)

    def set_voltage(self, level_v: float) -> None:
        alias = self._channel.alias
        self._write(f"{alias}.source.levelv = {level_v}")

    def set_current_limit(self, current_limit_a: float) -> None:
        alias = self._channel.alias
        self._write(f"{alias}.source.limiti = {current_limit_a}")

    def quick_set_source(self, *, level_v: Optional[float] = None, current_limit_a: Optional[float] = None) -> bool:
        """Adjust voltage and/or current limit without toggling output."""
        alias = self._channel.alias
        commands: list[str] = []
        if level_v is not None:
            commands.append(f"{alias}.source.levelv = {level_v}")
        if current_limit_a is not None:
            commands.append(f"{alias}.source.limiti = {current_limit_a}")
        if commands:
            self._batch_write(commands)
        return self.read_compliance()

    def ramp_to_voltage(
        self,
        target_v: float,
        *,
        step_v: float,
        dwell_s: float,
        current_limit_a: Optional[float] = None,
        progress: Optional[Callable[[float, Optional[float]], None]] = None,
    ) -> bool:
        """Ramp the output to target_v in step_v increments with dwell_s delays.

        The optional progress callback receives the commanded level and the measured
        voltage after each step so callers can surface real-time feedback.
        """
        if step_v <= 0:
            raise ValueError("step_v must be positive")
        if dwell_s < 0:
            raise ValueError("dwell_s must be non-negative")
        alias = self._channel.alias
        current_level = float(self._transport.query(f"print({alias}.source.levelv)") or 0.0)
        delta = target_v - current_level
        if abs(delta) <= step_v:
            compliance = self.quick_set_source(level_v=target_v, current_limit_a=current_limit_a)
            reading = self._safe_measure_voltage()
            if progress is not None:
                progress(target_v, reading)
            return compliance
        steps = int(abs(delta) // step_v)
        if abs(delta) % step_v:
            steps += 1
        direction = 1 if delta > 0 else -1
        level = current_level
        compliance = False
        for i in range(steps):
            remaining = target_v - level
            increment = direction * min(step_v, abs(remaining))
            level += increment
            compliance = self.quick_set_source(
                level_v=level, current_limit_a=current_limit_a if i == 0 else None
            ) or compliance
            reading = self._safe_measure_voltage()
            if progress is not None:
                progress(level, reading)
            if dwell_s:
                time.sleep(dwell_s)
        return compliance

    def ramp_to_zero(
        self,
        *,
        step_v: float,
        dwell_s: float,
        tolerance_v: float,
        current_limit_a: Optional[float] = None,
        progress: Optional[Callable[[float, Optional[float]], None]] = None,
    ) -> bool:
        """Bring the output to ~0 V using ramped steps before disabling it."""
        alias = self._channel.alias
        current_level = float(self._transport.query(f"print({alias}.source.levelv)") or 0.0)
        if abs(current_level) <= tolerance_v:
            return False
        target = 0.0
        compliance = self.ramp_to_voltage(
            target,
            step_v=step_v,
            dwell_s=dwell_s,
            current_limit_a=current_limit_a,
            progress=progress,
        )
        # Final trim if still beyond tolerance.
        current_level = float(self._transport.query(f"print({alias}.source.levelv)") or 0.0)
        if abs(current_level) > tolerance_v:
            self.quick_set_source(level_v=0.0, current_limit_a=current_limit_a)
        return compliance

    def enable_output(self, enabled: bool) -> None:
        alias = self._channel.alias
        state = "OUTPUT_ON" if enabled else "OUTPUT_OFF"
        self._write(f"{alias}.source.output = {alias}.{state}")

    def read_compliance(self) -> bool:
        alias = self._channel.alias
        response = self._transport.query(f"print({alias}.source.compliance)")
        return response.strip() in {"1", "true", "True"}

    def drain_error_queue(self) -> list[ErrorEntry]:
        """Retrieve and clear the instrument error queue."""
        entries: list[ErrorEntry] = []
        try:
            count_resp = self._transport.query("print(errorqueue.count)")
        except Exception as exc:
            raise RuntimeError(f"Failed to read error count: {exc}") from exc
        try:
            count = int((count_resp or "0").strip() or "0")
        except ValueError:
            count = 0
        if count <= 0:
            return entries
        script = (
            "local code, msg, severity, node = errorqueue.next();"
            "if code then print(string.format('%d|%s|%d|%d', code, msg, severity, node)) end"
        )
        for _ in range(count):
            response = self._transport.query(script)
            text_resp = response.strip()
            if not text_resp:
                continue
            parts = text_resp.split("|", 3)
            if len(parts) != 4:
                continue
            code, message, severity, node = parts
            try:
                entries.append(ErrorEntry(int(code), message, int(severity), int(node)))
            except ValueError:
                continue
        return entries

    def set_beeper_enabled(self, enabled: bool) -> None:
        """Enable or disable the front-panel beeper."""
        state = "beeper.ON" if enabled else "beeper.OFF"
        self._write(f"beeper.enable = {state}")

    def beep(self, duration: float = 0.2, frequency_hz: int = 1200) -> None:
        """Issue an audible beep for feedback when toggling output."""
        self._write(f"beeper.beep({duration}, {frequency_hz})")

    def configure_display_for_voltage(self) -> None:
        """Mirror the selected channel and show voltage on the front-panel display."""
        alias = self._channel.alias
        channel_constant = alias.upper()
        commands = [
            f"display.screen = display.{channel_constant}",
            f"display.{alias}.measure.func = display.MEASURE_DCVOLTS",
        ]
        self._batch_write(commands)

    def measure_voltage(self) -> float:
        """Trigger a voltage measurement and return the reading."""
        alias = self._channel.alias
        response = self._transport.query(f"print({alias}.measure.v())")
        try:
            return float(response)
        except ValueError as exc:
            raise ValueError(f"Unexpected voltage reading: {response!r}") from exc

    def _write(self, command: str) -> None:
        if not self._connected:
            raise RuntimeError("Instrument is not connected")
        self._transport.write(command)

    def _batch_write(self, commands: Iterable[str]) -> None:
        for command in commands:
            self._write(command)

    def _safe_measure_voltage(self) -> Optional[float]:
        try:
            return self.measure_voltage()
        except Exception:
            return None



def list_gpib_resources(resource_manager: Optional["pyvisa.ResourceManager"] = None) -> list[str]:
    """Return GPIB resource strings discovered by the active VISA installation."""
    try:
        import pyvisa
    except ImportError:
        return []

    try:
        rm = resource_manager or pyvisa.ResourceManager()
    except (pyvisa.errors.VisaIOError, OSError):
        return []

    try:
        resources = rm.list_resources()
    except pyvisa.errors.VisaIOError:
        return []
    return sorted(res for res in resources if res.upper().startswith("GPIB"))
