#!/usr/bin/env python3
"""Interactive command-line interface for controlling a ValveBank."""
import argparse

from IO_master import IO_master
from devices.ValveBank_SY3000 import ValveBank


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open a ValveBank controller and toggle valves interactively"
    )
    parser.add_argument(
        "--ip", default="192.168.1.250", help="IP address of the IO master"
    )
    parser.add_argument(
        "--port", type=int, default=502, help="TCP port of the IO master"
    )
    parser.add_argument(
        "--device-port", type=int, default=1, help="IO port number for the valve bank"
    )
    args = parser.parse_args()

    io = IO_master(args.ip, SERVER_PORT=args.port)
    vb = ValveBank(io, port_number=args.device_port)

    print("Valve bank controller ready.")
    print("Commands: on VALVE [DURATION] | off VALVE [VALVE...] | alloff | exit")
    print("Examples: 'on 1.A', 'on 1.B 3', 'off 1.A', 'alloff', 'exit')")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()

        try:
            if cmd == "exit":
                break
            elif cmd == "alloff":
                vb.all_off()
            elif cmd == "on" and len(parts) >= 2:
                valve = parts[1]
                dur = float(parts[2]) if len(parts) >= 3 else None
                vb.valve_on(valve, duration=dur)
            elif cmd == "off" and len(parts) >= 2:
                vb.valve_off(*parts[1:])
            else:
                print("Unknown command")
        except Exception as exc:  # pragma: no cover - user input errors
            print(f"Error: {exc}")

    vb.all_off()
    io.close_client()


if __name__ == "__main__":
    main()
