"""Utility script for reading load cell data.

This module ties together the IO master, AL2205 hub and LCM300 load cell
interfaces to provide a simple command line utility.  All low level load cell
interaction is handled by :mod:`LoadCell_LCM300` so that this script simply
coordinates the devices and prints results.
"""

import argparse
from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300


def readLC(cells, unit, x=None):
    """Print load cell forces in the requested unit.

    Parameters
    ----------
    cells : list[LoadCellLCM300]
        Sequence of load cell objects to read.
    unit : {"lbf", "N"}
        Desired output units.
    x : int or None, optional
        Load cell number to read (1 indexed).  Reads all cells when ``None``.
    """
    label = "N" if unit.lower() == "n" else "lbf"

    def _print_cell(idx: int) -> None:
        force = cells[idx].read_force(unit)
        if force is None:
            print(f"load cell {idx + 1}: N/A")
        else:
            print(f"load cell {idx + 1}: {force:.2f}{label}")

    if x is None:
        for i in range(len(cells)):
            _print_cell(i)
    else:
        if not 1 <= x <= len(cells):
            raise ValueError("Load cell number must be between 1 and 5")
        _print_cell(x - 1)


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
    parser.add_argument(
        "--cell",
        type=int,
        default=None,
        help="Load cell number to read (1-5). Reads all if omitted.",
    )
    args = parser.parse_args()

    io = IO_master(args.ip)
    hub = AL2205Hub(io, port_number=args.hub_port)

    cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]

    readLC(cells, args.unit, args.cell)

    io.close_client()


if __name__ == "__main__":
    main()
