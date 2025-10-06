#!/usr/bin/env python
"""Interactive helpers to replicate manual front-panel tests on the Keithley 2612."""
from __future__ import annotations

import argparse
from typing import Callable

from keithley2612 import Channel, Keithley2612Controller, VoltageConfig
from keithley2612.transport import SimulatedTransport, VisaTransport


def build_controller(resource: str) -> Keithley2612Controller:
    if resource.lower().startswith("sim"):
        transport = SimulatedTransport()
    else:
        transport = VisaTransport(resource)
    return Keithley2612Controller(transport)


def step_one(controller: Keithley2612Controller, channel: Channel) -> None:
    controller.set_beeper_enabled(True)
    controller.select_channel(channel)
    controller.configure_display_for_voltage()
    controller.configure_voltage_source(
        VoltageConfig(level_v=1.0, current_limit_a=5e-3, autorange=True)
    )
    controller.enable_output(True)
    reading = controller.measure_voltage()
    print(
        f"Step 1: Output enabled ({channel.name}) at 1.000 V; immediate readback {reading:.6f} V."
        " Observe the panel for 'SrcX:+1.000V'."
    )


def step_two(controller: Keithley2612Controller, channel: Channel) -> None:
    controller.set_beeper_enabled(True)
    controller.enable_output(False)
    controller.beep(0.3, 1200)
    print("Step 2: Output explicitly disabled and manual beep requested.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "resource",
        nargs="?",
        default="sim://2612",
        help="VISA resource identifier (e.g. GPIB0::26::INSTR)",
    )
    parser.add_argument(
        "--channel",
        choices=["A", "B"],
        default="A",
        help="SMU channel to exercise",
    )
    args = parser.parse_args()

    controller = build_controller(args.resource)
    channel = Channel[args.channel]

    controller.connect()
    try:
        actions: dict[str, Callable[[], None]] = {
            "1": lambda: step_one(controller, channel),
            "2": lambda: step_two(controller, channel),
            "q": lambda: None,
        }
        prompt = "Enter 1 (apply 1V), 2 (beep/off), or q (quit): "
        while True:
            choice = input(prompt).strip().lower()
            if choice not in actions:
                print("Unrecognised option. Choose 1, 2, or q.")
                continue
            if choice == "q":
                break
            actions[choice]()
    finally:
        controller.enable_output(False)
        controller.disconnect()
        print("Disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
