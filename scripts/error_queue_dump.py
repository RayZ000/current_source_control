#!/usr/bin/env python
"""Print and clear the Keithley 2612 error queue."""
from __future__ import annotations

import argparse

from keithley2612.controller import Keithley2612Controller
from keithley2612.transport import SimulatedTransport, VisaTransport


def build_controller(resource: str) -> Keithley2612Controller:
    if resource.lower().startswith("sim"):
        transport = SimulatedTransport()
    else:
        transport = VisaTransport(resource)
    return Keithley2612Controller(transport)


def pop_error(transport) -> str:
    cmd = (
        "local code, msg, severity, node = errorqueue.next() "
        "if code then print(string.format('%d|%s|%d|%d', code, msg, severity, node)) end"
    )
    return transport.query(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", help="VISA resource (e.g. GPIB0::26::INSTR)")
    args = parser.parse_args()

    controller = build_controller(args.resource)
    controller.connect()
    try:
        transport = controller._transport  # type: ignore[attr-defined]
        lines = []
        while True:
            result = pop_error(transport).strip()
            if not result:
                break
            lines.append(result)
        if not lines:
            print("Error queue empty")
        else:
            for line in lines:
                print(line)
    finally:
        controller.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
