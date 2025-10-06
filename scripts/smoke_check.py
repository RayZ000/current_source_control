#!/usr/bin/env python
"""Minimal connectivity script for validating VISA access to the 2612."""
from __future__ import annotations

import argparse
from typing import Optional

from keithley2612 import Channel, Keithley2612Controller, VoltageConfig
from keithley2612.transport import SimulatedTransport, VisaTransport


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", nargs="?", default="sim://2612", help="VISA resource string or sim://2612")
    parser.add_argument("--channel", choices=["A", "B"], default="A", help="SMU channel to exercise")
    parser.add_argument("--voltage", type=float, default=0.0, help="Voltage level to set during the check")
    parser.add_argument(
        "--current-limit",
        type=float,
        default=1e-3,
        help="Compliance current in amps to use when enabling the source",
    )
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
    controller.connect()
    channel = Channel[f"{args.channel}"]
    controller.select_channel(channel)
    print(f"Connected to {controller.identify()} via {args.resource}")
    controller.reset()
    controller.configure_voltage_source(
        VoltageConfig(level_v=args.voltage, current_limit_a=args.current_limit, autorange=True)
    )
    controller.enable_output(True)
    print(
        f"Output enabled on {channel.name} at {args.voltage:.3f} V with {args.current_limit:.6f} A limit",
    )
    controller.enable_output(False)
    controller.disconnect()
    print("Output disabled and connection closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
