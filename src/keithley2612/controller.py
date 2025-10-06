"""High-level Keithley 2612 controller built on top of a transport layer."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from .transport import InstrumentTransport


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

    def enable_output(self, enabled: bool) -> None:
        alias = self._channel.alias
        state = "OUTPUT_ON" if enabled else "OUTPUT_OFF"
        self._write(f"{alias}.source.output = {alias}.{state}")

    def read_compliance(self) -> bool:
        alias = self._channel.alias
        response = self._transport.query(f"print({alias}.source.compliance)")
        return response.strip() in {"1", "true", "True"}

    def _write(self, command: str) -> None:
        if not self._connected:
            raise RuntimeError("Instrument is not connected")
        self._transport.write(command)

    def _batch_write(self, commands: Iterable[str]) -> None:
        for command in commands:
            self._write(command)



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
