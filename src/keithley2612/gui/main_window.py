"""Main window for the Keithley 2612 control GUI."""
from __future__ import annotations

from typing import Iterable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setApplicationName("Keithley 2612 Controller")
    return app


class MainWindow(QMainWindow):
    """Top-level window exposing signals for controller integration."""

    refresh_requested = pyqtSignal()
    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()
    channel_changed = pyqtSignal(str)
    apply_requested = pyqtSignal(float, float, bool)
    quick_change_requested = pyqtSignal(float, float)
    output_toggled = pyqtSignal(bool)
    voltage_changed = pyqtSignal(float)
    current_limit_changed = pyqtSignal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Keithley 2612 Controller")
        self._build_ui()

    def populate_resources(self, resources: Iterable[str]) -> None:
        current = self.resource_combo.currentText()
        self.resource_combo.blockSignals(True)
        self.resource_combo.clear()
        for resource in resources:
            self.resource_combo.addItem(resource)
        if current and current in resources:
            index = self.resource_combo.findText(current)
            if index >= 0:
                self.resource_combo.setCurrentIndex(index)
        self.resource_combo.blockSignals(False)

    def set_connection_state(self, connected: bool) -> None:
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.resource_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)
        self.output_button.setEnabled(connected)
        self.apply_button.setEnabled(connected and not self.output_button.isChecked() and not self.safe_ramp_check.isChecked())
        self.quick_button.setEnabled(connected)
        self.safe_ramp_check.setEnabled(connected)
        self.safe_shutdown_check.setEnabled(connected)
        self._update_safe_control_states()
        if not connected:
            self.safe_shutdown_check.setChecked(True)
            self._update_safe_control_states()
        self.channel_a.setEnabled(connected)
        self.channel_b.setEnabled(connected)
        self.autorange_check.setEnabled(connected)
        self.voltage_spin.setEnabled(connected)
        self.current_limit_spin.setEnabled(connected)
        if not connected:
            self.output_button.setChecked(False)
            self.output_button.setText("Enable Output")

    def set_output_state(self, enabled: bool) -> None:
        self.output_button.setChecked(enabled)
        self.output_button.setText("Disable Output" if enabled else "Enable Output")

    def set_selected_channel(self, channel_alias: str) -> None:
        if channel_alias.lower() == "smub":
            self.channel_b.setChecked(True)
        else:
            self.channel_a.setChecked(True)

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def set_compliance_status(self, in_compliance: bool) -> None:
        status = "Compliance OK" if in_compliance else "Compliance TRIPPED"
        style = "color: green;" if in_compliance else "color: red;"
        self.compliance_label.setText(status)
        self.compliance_label.setStyleSheet(style)

    def set_voltage_value(self, value: float) -> None:
        with _SignalBlocker(self.voltage_spin):
            self.voltage_spin.setValue(value)

    def set_current_limit_value(self, value: float) -> None:
        with _SignalBlocker(self.current_limit_spin):
            self.current_limit_spin.setValue(value)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._build_resource_group())
        layout.addWidget(self._build_channel_group())
        layout.addWidget(self._build_source_group())
        layout.addWidget(self._build_log_group(), stretch=1)
        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.compliance_label = QLabel("Compliance OK")
        self.compliance_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_bar.addPermanentWidget(self.compliance_label)
        self.set_connection_state(False)

    def _build_resource_group(self) -> QGroupBox:
        group = QGroupBox("Instrument Connection")
        layout = QHBoxLayout(group)
        self.resource_combo = QComboBox()
        self.resource_combo.setEditable(True)
        layout.addWidget(QLabel("GPIB Address:"))
        layout.addWidget(self.resource_combo, stretch=1)
        self.refresh_button = QPushButton("Refresh")
        layout.addWidget(self.refresh_button)
        self.connect_button = QPushButton("Connect")
        layout.addWidget(self.connect_button)
        self.disconnect_button = QPushButton("Disconnect")
        layout.addWidget(self.disconnect_button)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.connect_button.clicked.connect(self._emit_connect)
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        return group

    def _emit_connect(self) -> None:
        resource = self.resource_combo.currentText().strip()
        if resource:
            self.connect_requested.emit(resource)

    def _build_channel_group(self) -> QGroupBox:
        group = QGroupBox("Channel")
        layout = QHBoxLayout(group)
        self.channel_a = QRadioButton("Channel A")
        self.channel_b = QRadioButton("Channel B")
        self.channel_a.setChecked(True)
        layout.addWidget(self.channel_a)
        layout.addWidget(self.channel_b)
        self.channel_a.toggled.connect(lambda checked: checked and self.channel_changed.emit("smua"))
        self.channel_b.toggled.connect(lambda checked: checked and self.channel_changed.emit("smub"))
        return group

    def _build_source_group(self) -> QGroupBox:
        group = QGroupBox("Voltage Source")
        layout = QVBoxLayout(group)

        form_layout = QHBoxLayout()
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(-200.0, 200.0)
        self.voltage_spin.setDecimals(3)
        self.voltage_spin.setSuffix(" V")
        self.voltage_spin.setValue(0.0)
        self.voltage_spin.valueChanged.connect(self.voltage_changed.emit)
        form_layout.addWidget(QLabel("Level"))
        form_layout.addWidget(self.voltage_spin)

        self.current_limit_spin = QDoubleSpinBox()
        self.current_limit_spin.setRange(0.0, 1.0)
        self.current_limit_spin.setDecimals(6)
        self.current_limit_spin.setSuffix(" A")
        self.current_limit_spin.setValue(0.001)
        self.current_limit_spin.valueChanged.connect(self.current_limit_changed.emit)
        form_layout.addWidget(QLabel("Current Limit"))
        form_layout.addWidget(self.current_limit_spin)

        self.autorange_check = QCheckBox("Autorange")
        self.autorange_check.setChecked(True)
        form_layout.addWidget(self.autorange_check)
        form_layout.addStretch()
        layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        self.apply_button = QPushButton("Apply Settings")
        button_row.addWidget(self.apply_button)
        self.quick_button = QPushButton("Quick Change")
        button_row.addWidget(self.quick_button)
        self.output_button = QPushButton("Enable Output")
        self.output_button.setCheckable(True)
        button_row.addWidget(self.output_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        ramp_row = QHBoxLayout()
        self.safe_ramp_check = QCheckBox("Safe Ramp")
        ramp_row.addWidget(self.safe_ramp_check)
        ramp_row.addWidget(QLabel("Step"))
        self.ramp_step_spin = QDoubleSpinBox()
        self.ramp_step_spin.setRange(0.001, 1000.0)
        self.ramp_step_spin.setDecimals(3)
        self.ramp_step_spin.setValue(5.0)
        self.ramp_step_spin.setSuffix(" V")
        ramp_row.addWidget(self.ramp_step_spin)
        ramp_row.addWidget(QLabel("Dwell"))
        self.ramp_dwell_spin = QDoubleSpinBox()
        self.ramp_dwell_spin.setRange(0.0, 10.0)
        self.ramp_dwell_spin.setDecimals(3)
        self.ramp_dwell_spin.setValue(0.1)
        self.ramp_dwell_spin.setSuffix(" s")
        ramp_row.addWidget(self.ramp_dwell_spin)
        self.safe_shutdown_check = QCheckBox("Safe Shutdown")
        self.safe_shutdown_check.setChecked(True)
        ramp_row.addWidget(self.safe_shutdown_check)
        self.shutdown_tol_spin = QDoubleSpinBox()
        self.shutdown_tol_spin.setRange(0.1, 50.0)
        self.shutdown_tol_spin.setDecimals(2)
        self.shutdown_tol_spin.setValue(5.0)
        self.shutdown_tol_spin.setSuffix(" V tol")
        ramp_row.addWidget(self.shutdown_tol_spin)
        ramp_row.addStretch()
        layout.addLayout(ramp_row)

        self.apply_button.clicked.connect(self._emit_apply)
        self.quick_button.clicked.connect(self._emit_quick_change)
        self.output_button.toggled.connect(self._emit_output_toggle)
        self.safe_ramp_check.toggled.connect(self._update_safe_control_states)
        self.safe_shutdown_check.toggled.connect(self._update_safe_control_states)
        self._update_safe_control_states()
        return group

    def _emit_apply(self) -> None:
        self.apply_requested.emit(
            self.voltage_spin.value(),
            self.current_limit_spin.value(),
            self.autorange_check.isChecked(),
        )

    def _emit_quick_change(self) -> None:
        self.quick_change_requested.emit(
            self.voltage_spin.value(),
            self.current_limit_spin.value(),
        )

    def _emit_output_toggle(self, enabled: bool) -> None:
        self.output_button.setText("Disable Output" if enabled else "Enable Output")
        self.output_toggled.emit(enabled)

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Event Log")
        layout = QVBoxLayout(group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        return group


    def _update_safe_control_states(self) -> None:
        check = self.safe_ramp_check.isChecked() or self.safe_shutdown_check.isChecked()
        self.ramp_step_spin.setEnabled(check)
        self.ramp_dwell_spin.setEnabled(check)
        self.shutdown_tol_spin.setEnabled(self.safe_shutdown_check.isChecked())

    def safe_ramp_enabled(self) -> bool:
        return self.safe_ramp_check.isChecked()

    def safe_ramp_step(self) -> float:
        return self.ramp_step_spin.value()

    def safe_ramp_dwell(self) -> float:
        return self.ramp_dwell_spin.value()

    def safe_shutdown_enabled(self) -> bool:
        return self.safe_shutdown_check.isChecked()

    def safe_shutdown_tolerance(self) -> float:
        return self.shutdown_tol_spin.value()


class _SignalBlocker:
    """Context manager to temporarily block signals on a widget."""

    def __init__(self, widget: QWidget) -> None:
        self._widget = widget
        self._previous = False

    def __enter__(self) -> None:
        self._previous = self._widget.blockSignals(True)

    def __exit__(self, exc_type, exc, tb) -> None:
        self._widget.blockSignals(self._previous)
