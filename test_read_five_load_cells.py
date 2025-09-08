import argparse
from IO_master import IO_master
from devices.AL2205_Hub import AL2205Hub
from devices.LoadCell_LCM300 import LoadCellLCM300


def main():
    parser = argparse.ArgumentParser(
        description="Read force data from five load cells on an AL2205 hub"
    )
    parser.add_argument(
        "ip",
        help="IP address of the AL1342 IO master",
    )
    parser.add_argument(
        "--hub-port",
        type=int,
        default=1,
        help="AL1342 port number where the AL2205 hub is connected (1-8)",
    )
    parser.add_argument(
        "--unit",
        choices=["lbf", "N"],
        default="N",
        help="Force units to display",
    )
    args = parser.parse_args()

    io = IO_master(args.ip)
    hub = AL2205Hub(io, port_number=args.hub_port)

    cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]

    label = "N" if args.unit.lower() == "n" else "lbf"
    for i, cell in enumerate(cells, start=1):
        force = cell.read_force(args.unit)
        if force is None:
            print(f"load cell {i}: N/A")
        else:
            print(f"load cell {i}: {force:.2f}{label}")

    io.close_client()


if __name__ == "__main__":
    main()
