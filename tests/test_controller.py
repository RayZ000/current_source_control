import pytest

from keithley2612 import Channel, Keithley2612Controller, VoltageConfig
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
