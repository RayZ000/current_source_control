#!/usr/bin/env python
"""Exercise beeper and front-panel display behaviour for the Keithley 2612."""
from __future__ import annotations

import argparse

from keithley2612 import Channel, Keithley2612Controller, VoltageConfig
from keithley2612.transport import SimulatedTransport, VisaTransport


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", nargs="?", default="sim://2612", help="VISA resource (e.g. GPIB0::26::INSTR)")
    parser.add_argument("--channel", choices=["A", "B"], default="A", help="Channel to verify")
    parser.add_argument("--voltage", type=float, default=1.0, help="Voltage level to apply")
    parser.add_argument("--current-limit", type=float, default=5e-3, help="Compliance current in amps")
    parser.add_argument("--duration", type=float, default=0.2, help="Beep duration in seconds")
    parser.add_argument("--frequency", type=int, default=1200, help="Beep frequency in Hz")
    return parser.parse_args()


def build_controller(resource: str) -> Keithley2612Controller:
    if resource.lower().startswith("sim"):
        transport = SimulatedTransport()
    else:
        transport = VisaTransport(resource)
    return Keithley2612Controller(transport)


def main() -> int:
    args = parse_args()
    controller = build_controller(args.resource)
    channel = Channel[args.channel]

    controller.connect()
    controller.set_beeper_enabled(True)
    controller.select_channel(channel)
    controller.configure_display_for_voltage()
    controller.configure_voltage_source(
        VoltageConfig(level_v=args.voltage, current_limit_a=args.current_limit, autorange=True)
    )
    controller.enable_output(True)
    reading = controller.measure_voltage()
    controller.beep(args.duration, args.frequency)

    print(f"Output enabled on {channel.name} at {args.voltage:.3f} V (readback {reading:.3f} V).")
    print("Confirm on the front panel that the voltage is displayed and a beep was heard.")

    controller.enable_output(False)
    controller.beep(args.duration, args.frequency)
    controller.disconnect()
    print("Output disabled; you should have heard a second beep.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
