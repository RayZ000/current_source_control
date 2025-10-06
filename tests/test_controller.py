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
