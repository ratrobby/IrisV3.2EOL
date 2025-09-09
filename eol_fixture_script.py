"""EOL Fixture Script

This single-file utility communicates with an AL2205 hub connected to an
AL1342 IO master.  Five LCM300 load cells are attached to the hub on ports
X1.0 through X1.4.  The script provides helper functions and a small command
line interface to read individual load cells, read all load cells at once,
and display a simple monitoring window.

The AL1342 is assumed to use IP address 192.168.1.1 and the AL2205 hub is
connected to port X01 on the AL1342.
"""

from __future__ import annotations

import argparse
import time
from typing import Optional

try:  # Optional dependency; a stub is provided when unavailable
    from pyModbusTCP.client import ModbusClient
except Exception:  # pragma: no cover - dependency may be missing
    class ModbusClient:  # type: ignore
        """Fallback stub when pyModbusTCP is not installed."""

        def __init__(self, *args, **kwargs):
            pass

        def open(self):  # pragma: no cover - simple stub
            return True

        def close(self):  # pragma: no cover - simple stub
            pass

        def read_holding_registers(self, register, count):  # pragma: no cover
            return [0] * count

# Tkinter is used for the monitoring window.  The script still works without it.
try:  # pragma: no cover - optional GUI dependency
    import tkinter as tk
    from tkinter import ttk
except Exception:  # pragma: no cover
    tk = None  # type: ignore
    ttk = None  # type: ignore

IP_ADDR = "192.168.1.1"  # AL1342 IP address
PORT_NUMBER = 1  # AL2205 connected to X01

# Static register maps copied from the multi-module implementation
READ_REGISTER_MAP = {
    1: 1002,
    2: 2002,
    3: 3002,
    4: 4002,
    5: 5002,
    6: 6002,
    7: 7002,
    8: 8002,
}

WORD_MAP = {
    0: 1,
    1: 4,
    2: 5,
    3: 6,
    4: 7,
    5: 8,
    6: 9,
    7: 10,
}


def _get_client() -> ModbusClient:
    client = ModbusClient(host=IP_ADDR, port=502, timeout=1.0)
    if not client.open():
        raise ConnectionError(f"Unable to connect to Modbus server at {IP_ADDR}:502")
    return client


def _read_force(client: ModbusClient, x1_index: int, unit: str = "N") -> Optional[float]:
    base_register = READ_REGISTER_MAP[PORT_NUMBER]
    word_offset = WORD_MAP.get(x1_index)
    if word_offset is None:
        raise ValueError("Invalid X1 index. Must be between 0 and 7.")
    register = base_register + word_offset
    word = client.read_holding_registers(register, 1)
    raw = word[0] if word else None
    if raw is None:
        return None
    voltage = raw / 1000
    force_lbf = (5.0 - voltage) * 5
    if unit.lower() == "n":
        return force_lbf * 4.44822
    return force_lbf


def read_load_cell(cell_number: int, unit: str = "N") -> None:
    """Read a single load cell and print the force value."""
    if not 1 <= cell_number <= 5:
        raise ValueError("Load cell number must be between 1 and 5")
    client = _get_client()
    try:
        force = _read_force(client, cell_number - 1, unit)
        label = "N" if unit.lower() == "n" else "lbf"
        if force is None:
            print(f"load cell {cell_number}: N/A")
        else:
            print(f"load cell {cell_number}: {force:.2f}{label}")
    finally:
        client.close()


def read_all_load_cells(unit: str = "N") -> None:
    """Read all five load cells and print their force values."""
    client = _get_client()
    try:
        for i in range(5):
            force = _read_force(client, i, unit)
            label = "N" if unit.lower() == "n" else "lbf"
            if force is None:
                print(f"load cell {i + 1}: N/A")
            else:
                print(f"load cell {i + 1}: {force:.2f}{label}")
    finally:
        client.close()


def monitor_load_cells(unit: str = "N") -> None:
    """Open a popup window and continuously display all five load cells."""
    if tk is None:
        print("Tkinter is required for the monitoring window but is not available.")
        return

    client = _get_client()

    try:
        root = tk.Tk()
        root.title("Load Cell Monitor")

        labels = []
        for i in range(5):
            lbl = ttk.Label(root, text=f"Cell {i + 1}: --")
            lbl.pack(padx=10, pady=5)
            labels.append(lbl)

        def update() -> None:
            for i in range(5):
                force = _read_force(client, i, unit)
                label = "N" if unit.lower() == "n" else "lbf"
                if force is None:
                    text = f"Cell {i + 1}: N/A"
                else:
                    text = f"Cell {i + 1}: {force:.2f}{label}"
                labels[i].config(text=text)
            root.after(500, update)

        update()
        root.mainloop()
    except Exception as exc:  # pragma: no cover - GUI related
        print(f"Unable to open monitoring window: {exc}")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="EOL Fixture Script")
    parser.add_argument("--cell", type=int, help="Read a single load cell (1-5)")
    parser.add_argument(
        "--all", action="store_true", help="Read all five load cells"
    )
    parser.add_argument(
        "--monitor", action="store_true", help="Open a monitoring window"
    )
    parser.add_argument(
        "--unit", choices=["lbf", "N"], default="N", help="Force units to display"
    )
    args = parser.parse_args()

    if args.monitor:
        monitor_load_cells(args.unit)
    elif args.all:
        read_all_load_cells(args.unit)
    elif args.cell:
        read_load_cell(args.cell, args.unit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
