"""Transport interfaces for communicating with a Keithley 2612 instrument."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


class InstrumentTransport(Protocol):
    """Minimal transport interface used by the controller."""

    def open(self) -> None:
        """Open the underlying connection."""

    def close(self) -> None:
        """Close the underlying connection."""

    def write(self, command: str) -> None:
        """Send a command without expecting a response."""

    def query(self, command: str) -> str:
        """Send a command and return the response."""


class VisaTransport:
    """PyVISA-backed transport."""

    def __init__(
        self,
        resource_name: str,
        resource_manager: Optional["pyvisa.ResourceManager"] = None,
        *,
        timeout_ms: int = 5000,
    ) -> None:
        self.resource_name = resource_name
        self._resource_manager = resource_manager
        self.timeout_ms = timeout_ms
        self._resource = None

    def open(self) -> None:  # pragma: no cover - exercised during lab validation
        import pyvisa

        rm = self._resource_manager or pyvisa.ResourceManager()
        self._resource = rm.open_resource(self.resource_name)
        self._resource.timeout = self.timeout_ms
        self._resource.write_termination = "\n"
        self._resource.read_termination = "\n"

    def close(self) -> None:  # pragma: no cover - exercised during lab validation
        if self._resource is not None:
            self._resource.close()
            self._resource = None

    def write(self, command: str) -> None:  # pragma: no cover - exercised during lab validation
        if self._resource is None:
            raise RuntimeError("Transport is not open")
        self._resource.write(command)

    def query(self, command: str) -> str:  # pragma: no cover - exercised during lab validation
        if self._resource is None:
            raise RuntimeError("Transport is not open")
        return str(self._resource.query(command)).strip()


@dataclass
class _ChannelState:
    func: str = "OUTPUT_DCVOLTS"
    autorange: bool = True
    level_v: float = 0.0
    limit_i: float = 1e-3
    output_on: bool = False
    compliance: bool = False


@dataclass
class SimulatedTransport:
    """Simple in-memory simulator for local development without hardware."""

    identity: str = "Keithley Instruments Inc., Model 2612, 1234567, FW-1.0"
    timeout_ms: int = 5000
    _is_open: bool = field(default=False, init=False)
    _channels: dict[str, _ChannelState] = field(
        default_factory=lambda: {"smua": _ChannelState(), "smub": _ChannelState()},
        init=False,
    )

    def open(self) -> None:
        self._is_open = True

    def close(self) -> None:
        self._is_open = False

    def write(self, command: str) -> None:
        if not self._is_open:
            raise RuntimeError("Transport is not open")
        self._process_command(command.strip())

    def query(self, command: str) -> str:
        if not self._is_open:
            raise RuntimeError("Transport is not open")
        command = command.strip()
        if command == "*IDN?":
            return self.identity
        if command.startswith("print(") and command.endswith(")"):
            expr = command[len("print(") : -1]
            return self._evaluate_expression(expr)
        raise NotImplementedError(f"Simulator cannot handle query: {command}")

    def _process_command(self, command: str) -> None:
        if command == "":
            return
        if command == "*RST":
            for state in self._channels.values():
                state.__dict__.update(_ChannelState().__dict__)
            return
        if command.endswith("reset()"):
            channel = command.split(".")[0]
            self._channels[channel] = _ChannelState()
            return
        if "=" in command:
            lhs, rhs = [part.strip() for part in command.split("=", maxsplit=1)]
            channel, attribute = lhs.split(".", maxsplit=1)
            state = self._channels[channel]
            if attribute == "source.func":
                state.func = rhs.split(".")[-1]
                return
            if attribute == "source.autorangev":
                state.autorange = rhs.endswith("AUTORANGE_ON")
                return
            if attribute == "source.levelv":
                state.level_v = float(rhs)
                return
            if attribute == "source.limiti":
                state.limit_i = float(rhs)
                return
            if attribute == "source.output":
                state.output_on = rhs.endswith("OUTPUT_ON")
                return
        raise NotImplementedError(f"Simulator cannot handle command: {command}")

    def _evaluate_expression(self, expr: str) -> str:
        if expr.endswith(".source.compliance"):
            channel = expr.split(".")[0]
            state = self._channels[channel]
            return "1" if state.compliance else "0"
        raise NotImplementedError(f"Simulator cannot handle expression: {expr}")

    def set_compliance(self, channel: str, compliance: bool) -> None:
        self._channels[channel].compliance = compliance
