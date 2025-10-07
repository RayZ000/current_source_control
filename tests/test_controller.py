import pytest

from keithley2612 import Channel, ErrorEntry, Keithley2612Controller, VoltageConfig
from keithley2612.transport import SimulatedTransport


def test_configure_voltage_source_updates_simulator():
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.reset()
    controller.configure_voltage_source(VoltageConfig(level_v=1.5, current_limit_a=0.002))
    controller.set_voltage(2.0)
    controller.set_current_limit(0.003)
    controller.enable_output(True)

    state = transport._channels[Channel.A.value]  # accessing simulator internals for verification
    assert pytest.approx(state.level_v, rel=1e-6) == 2.0
    assert pytest.approx(state.limit_i, rel=1e-6) == 0.003
    assert state.output_on is True
    transport.set_compliance(Channel.A.value, True)
    assert controller.read_compliance() is True

    controller.enable_output(False)
    controller.disconnect()


def test_switching_channels_isolated_state():
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.reset()
    controller.select_channel(Channel.A)
    controller.configure_voltage_source(VoltageConfig(level_v=0.5, current_limit_a=0.001))
    controller.select_channel(Channel.B)
    controller.configure_voltage_source(VoltageConfig(level_v=1.2, current_limit_a=0.004))

    state_a = transport._channels[Channel.A.value]
    state_b = transport._channels[Channel.B.value]
    assert pytest.approx(state_a.level_v, rel=1e-6) == 0.5
    assert pytest.approx(state_b.level_v, rel=1e-6) == 1.2
    assert pytest.approx(state_b.limit_i, rel=1e-6) == 0.004

    controller.disconnect()


def test_beeper_and_display_configuration():
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.set_beeper_enabled(True)
    controller.configure_display_for_voltage()
    assert transport.beeper_enabled is True
    assert transport.display_screen == "SMUA"
    assert transport._channels[Channel.A.value].display_measure == "MEASURE_DCVOLTS"

    controller.beep(0.2, 1500)
    assert transport.last_beep == "beeper.beep(0.2, 1500)"

    transport._channels[Channel.A.value].level_v = 1.234
    assert controller.measure_voltage() == pytest.approx(1.234)

    controller.select_channel(Channel.B)
    controller.configure_display_for_voltage()
    assert transport.display_screen == "SMUB"
    assert transport._channels[Channel.B.value].display_measure == "MEASURE_DCVOLTS"

    transport._channels[Channel.B.value].level_v = 4.567
    assert controller.measure_voltage() == pytest.approx(4.567)

    controller.disconnect()


def test_drain_error_queue_returns_entries():
    transport = SimulatedTransport()
    transport.push_error((-286, 'Runtime error', 3, 0))
    controller = Keithley2612Controller(transport)
    controller.connect()
    entries = controller.drain_error_queue()
    assert entries == [ErrorEntry(-286, 'Runtime error', 3, 0)]
    # Subsequent call should be empty because queue is drained.
    assert controller.drain_error_queue() == []
    controller.disconnect()


def test_quick_set_source_updates_without_toggle():
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.reset()
    controller.configure_voltage_source(VoltageConfig(level_v=1.0, current_limit_a=0.001))
    controller.enable_output(True)

    controller.quick_set_source(level_v=2.5, current_limit_a=0.002)

    state = transport._channels[Channel.A.value]
    assert pytest.approx(state.level_v, rel=1e-6) == 2.5
    assert pytest.approx(state.limit_i, rel=1e-6) == 0.002
    assert state.output_on is True

    controller.disconnect()


def test_ramp_to_voltage_uses_steps():
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.reset()
    controller.configure_voltage_source(VoltageConfig(level_v=0.0, current_limit_a=0.005))
    controller.enable_output(True)

    result = controller.ramp_to_voltage(0.05, step_v=0.02, dwell_s=0.0, current_limit_a=0.005)
    assert result is False

    state = transport._channels[Channel.A.value]
    assert pytest.approx(state.level_v, rel=1e-6) == 0.05

    transport.set_compliance(Channel.A.value, True)
    result = controller.ramp_to_voltage(0.1, step_v=0.02, dwell_s=0.0, current_limit_a=0.005)
    assert result is True
    assert controller.read_compliance() is True
    controller.disconnect()


def test_ramp_to_voltage_honours_dwell(monkeypatch):
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.reset()
    controller.configure_voltage_source(VoltageConfig(level_v=0.0, current_limit_a=0.005))
    controller.enable_output(True)

    sleeps: list[float] = []
    monkeypatch.setattr("keithley2612.controller.time.sleep", lambda duration: sleeps.append(duration))

    controller.ramp_to_voltage(0.06, step_v=0.02, dwell_s=0.1, current_limit_a=0.005)

    state = transport._channels[Channel.A.value]
    assert pytest.approx(state.level_v, rel=1e-6) == 0.06
    assert sleeps == [0.1, 0.1, 0.1]

    controller.disconnect()


def test_ramp_to_zero_respects_tolerance():
    transport = SimulatedTransport()
    controller = Keithley2612Controller(transport)

    controller.connect()
    controller.reset()
    controller.configure_voltage_source(VoltageConfig(level_v=0.5, current_limit_a=0.001))
    controller.enable_output(True)

    controller.ramp_to_zero(step_v=0.2, dwell_s=0.0, tolerance_v=0.05, current_limit_a=0.001)
    state = transport._channels[Channel.A.value]
    assert abs(state.level_v) <= 0.05

    controller.disconnect()
