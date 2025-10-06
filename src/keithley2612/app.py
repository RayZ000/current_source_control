"""Glue code that wires the PyQt6 GUI to the instrument controller."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import Channel, Keithley2612Controller, VoltageConfig
from .transport import SimulatedTransport, VisaTransport
from .controller import list_gpib_resources
from .gui import MainWindow, create_application

_SIM_RESOURCE = "sim://2612"


@dataclass
class ConnectionState:
    resource: str
    controller: Keithley2612Controller


class Application:
    """Controller that binds GUI events to instrument actions."""

    def __init__(self, window: Optional[MainWindow] = None) -> None:
        self.app: QApplication = create_application()
        self.window = window or MainWindow()
        self._connection: Optional[ConnectionState] = None
        self._output_enabled: bool = False
        self._measurement_timer = QTimer()
        self._measurement_timer.setInterval(750)
        self._measurement_timer.timeout.connect(self._poll_measurement)
        self._wire_signals()
        self.window.show()
        self.refresh_resources()

    def run(self) -> int:
        return self.app.exec()

    # --- GUI signal handlers -------------------------------------------------

    def refresh_resources(self) -> None:
        resources = list_gpib_resources()
        if _SIM_RESOURCE not in resources:
            resources = [_SIM_RESOURCE, *resources]
        self.window.populate_resources(resources)
        if resources:
            message = "Discovered resources: " + ", ".join(resources)
        else:
            message = "No GPIB resources found"
        self.window.append_log(message)

    def handle_connect(self, resource: str) -> None:
        if self._connection is not None:
            self.window.append_log("Already connected; disconnect first to switch instruments.")
            return
        controller: Optional[Keithley2612Controller] = None
        try:
            controller = self._open_controller(resource)
            controller.connect()
            self._connection = ConnectionState(resource=resource, controller=controller)
            identity = controller.identify()
            self.window.append_log(f"Connected to {identity}")
            self.window.set_connection_state(True)
            self._output_enabled = False
            self._measurement_timer.stop()
            controller.set_beeper_enabled(True)
            controller.configure_display_for_voltage()
            controller.configure_voltage_source(
                VoltageConfig(
                    level_v=self.window.voltage_spin.value(),
                    current_limit_a=self.window.current_limit_spin.value() or 1e-3,
                    autorange=self.window.autorange_check.isChecked(),
                )
            )
            controller.enable_output(False)
            self.window.set_output_state(False)
            self.window.set_compliance_status(True)
            self._log_error_queue("Connect")
        except Exception as exc:  # pragma: no cover - PyQt runtime behaviour
            self._show_error("Failed to connect", str(exc))
            self.window.append_log(f"Connection error: {exc}")
            if controller is not None:
                try:
                    controller.disconnect()
                except Exception:
                    pass
            self._connection = None

    def handle_disconnect(self) -> None:
        if self._connection is None:
            return
        controller = self._connection.controller
        try:
            controller.enable_output(False)
        except Exception:
            pass
        controller.disconnect()
        self.window.append_log(f"Disconnected from {self._connection.resource}")
        self._connection = None
        self._output_enabled = False
        self._measurement_timer.stop()
        self.window.set_connection_state(False)
        self.window.set_compliance_status(True)

    def handle_channel_change(self, alias: str) -> None:
        if self._connection is None:
            return
        channel = Channel(alias)
        try:
            self._connection.controller.select_channel(channel)
            self._connection.controller.configure_display_for_voltage()
            self.window.append_log(f"Switched to {alias.upper()}")
            self._update_compliance()
        except Exception as exc:  # pragma: no cover - PyQt runtime behaviour
            self._show_error("Channel change failed", str(exc))
            self.window.append_log(f"Channel change error: {exc}")

    def handle_apply(self, level_v: float, current_limit: float, autorange: bool) -> None:
        if self._connection is None:
            self.window.append_log("Cannot apply settings while disconnected.")
            return
        controller = self._connection.controller
        try:
            controller.enable_output(False)
            controller.configure_voltage_source(
                VoltageConfig(level_v=level_v, current_limit_a=current_limit, autorange=autorange)
            )
            controller.configure_display_for_voltage()
            self._output_enabled = False
            self._measurement_timer.stop()
            self.window.append_log(
                f"Applied settings: {level_v:.3f} V, {current_limit:.6f} A, autorange={'on' if autorange else 'off'}"
            )
            self.window.set_output_state(False)
            self._update_compliance()
            self._log_error_queue("Apply Settings")
        except Exception as exc:  # pragma: no cover
            self._show_error("Apply failed", str(exc))
            self.window.append_log(f"Apply error: {exc}")

    def handle_output_toggle(self, enabled: bool) -> None:
        if self._connection is None:
            self.window.set_output_state(False)
            self.window.append_log("Cannot toggle output while disconnected.")
            return
        controller = self._connection.controller
        try:
            controller.enable_output(enabled)
            controller.configure_display_for_voltage()
            reading_msg = ""
            if enabled:
                try:
                    reading = controller.measure_voltage()
                except Exception as exc:  # pragma: no cover - requires hardware quirks
                    reading_msg = f" (voltage readback failed: {exc})"
                else:
                    reading_msg = f" (display reading ≈ {reading:.3f} V)"
                self._output_enabled = True
                if not self._measurement_timer.isActive():
                    self._measurement_timer.start()
            else:
                self._output_enabled = False
                self._measurement_timer.stop()
            controller.set_beeper_enabled(True)
            controller.beep(0.15, 1200)
            state = "enabled" if enabled else "disabled"
            self.window.append_log(f"Output {state} for {controller.channel.name}{reading_msg}")
            self._update_compliance()
            self._log_error_queue(f"Output {state}")
        except Exception as exc:  # pragma: no cover
            self._show_error("Output toggle failed", str(exc))
            self.window.append_log(f"Output toggle error: {exc}")
            self.window.set_output_state(False)
            self._output_enabled = False
            self._measurement_timer.stop()

    def handle_voltage_change(self, value: float) -> None:
        if self._connection is None:
            return
        self.window.status_bar.showMessage(f"Requested voltage: {value:.3f} V", 2000)

    def handle_current_limit_change(self, value: float) -> None:
        if self._connection is None:
            return
        self.window.status_bar.showMessage(f"Requested current limit: {value:.6f} A", 2000)

    # --- Internal helpers ----------------------------------------------------

    def _poll_measurement(self) -> None:
        if not self._output_enabled or self._connection is None:
            return
        controller = self._connection.controller
        try:
            reading = controller.measure_voltage()
        except Exception as exc:  # pragma: no cover - hardware specific
            self.window.status_bar.showMessage(f"Measurement failed: {exc}", 3000)
            self._log_error_queue("Measurement poll")
            return
        self.window.status_bar.showMessage(f"Measured voltage: {reading:.4f} V", 1500)
        self._log_error_queue("Measurement poll")

    def _log_error_queue(self, context: str) -> None:
        if self._connection is None:
            return
        controller = self._connection.controller
        try:
            entries = controller.drain_error_queue()
        except Exception as exc:  # pragma: no cover - VISA/firmware quirks
            self.window.append_log(f"{context}: unable to read error queue ({exc})")
            return
        if not entries:
            return
        for entry in entries:
            self.window.append_log("{}: instrument error {} (severity {}): {}".format(
                context, entry.code, entry.severity, entry.message
            ))

    def _wire_signals(self) -> None:
        self.window.refresh_requested.connect(self.refresh_resources)
        self.window.connect_requested.connect(self.handle_connect)
        self.window.disconnect_requested.connect(self.handle_disconnect)
        self.window.channel_changed.connect(self.handle_channel_change)
        self.window.apply_requested.connect(self.handle_apply)
        self.window.output_toggled.connect(self.handle_output_toggle)
        self.window.voltage_changed.connect(self.handle_voltage_change)
        self.window.current_limit_changed.connect(self.handle_current_limit_change)

    def _open_controller(self, resource: str) -> Keithley2612Controller:
        if resource.lower().startswith("sim"):
            transport = SimulatedTransport()
        else:
            transport = VisaTransport(resource)
        controller = Keithley2612Controller(transport)
        return controller

    def _update_compliance(self) -> None:
        if self._connection is None:
            return
        try:
            in_compliance = not self._connection.controller.read_compliance()
        except NotImplementedError:
            # Simulator has manual compliance control; assume OK unless set otherwise.
            in_compliance = True
        except Exception:  # pragma: no cover
            in_compliance = False
        self.window.set_compliance_status(in_compliance)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self.window, title, message)
        self.window.status_bar.showMessage(message, 5000)


def run_gui() -> int:
    app = Application()
    return app.run()
