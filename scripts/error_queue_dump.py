from keithley2612 import ErrorEntry, Keithley2612Controller
from keithley2612.transport import SimulatedTransport, VisaTransport


def build_controller(resource: str) -> Keithley2612Controller:
    if resource.lower().startswith("sim"):
        transport = SimulatedTransport()
    else:
        transport = VisaTransport(resource)
    return Keithley2612Controller(transport)


def format_entry(entry: ErrorEntry) -> str:
    return f"{entry.code}|{entry.message}|{entry.severity}|{entry.node}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", help="VISA resource (e.g. GPIB0::26::INSTR)")
    args = parser.parse_args()

    controller = build_controller(args.resource)
    controller.connect()
    try:
        entries = controller.drain_error_queue()
        if not entries:
            print("Error queue empty")
        else:
            for entry in entries:
                print(format_entry(entry))
    finally:
        controller.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
