#!/usr/bin/env python3
"""Run a predefined valve sequence while logging sensor data.

This script communicates directly with the AL1342 IO master and an attached
AL2205 hub. Load cell and position sensor readings are captured throughout the
entire test and written to a CSV log file.
"""

import argparse
import csv
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk

from IO_master import IO_master
from devices.ValveBank_SY3000 import ValveBank
from devices.PressureRegulator_ITV_1050 import PressureRegulatorITV1050
from devices.AL2205_Hub import AL2205Hub
from devices.LoadCell_LCM300 import LoadCellLCM300
from devices.PositionSensor_SDAT_MHS_M160 import PositionSensorSDATMHS_M160
from thread_utils import start_thread
from commands import Hold

# Event logging helpers
event_lock = threading.Lock()
event_message = ""


def record_event(msg: str) -> None:
    """Print ``msg`` and store it for the logger thread."""
    global event_message
    print(msg)
    with event_lock:
        event_message = msg


# ------------------------------ Helpers ------------------------------

def start_loadcell_monitor(stop_event, *cells, interval=0.1):
    """Open a small window displaying live load cell readings in Newtons."""

    def _run() -> None:
        root = tk.Tk()
        root.title("Load Cell Monitor")

        vars = []
        for col, cell in enumerate(cells):
            ttk.Label(root, text=f"Load Cell {col + 1} (N)").grid(row=0, column=col, padx=5, pady=5)
            var = tk.StringVar(value="0")
            ttk.Label(root, textvariable=var, width=8).grid(row=1, column=col, padx=5)
            vars.append((cell, var))

        def update() -> None:
            if stop_event.is_set():
                root.quit()
                return
            for cell, var in vars:
                val = cell._get_force_value("N")
                if val is None:
                    var.set("N/A")
                else:
                    var.set(f"{val:.2f}")
            root.after(int(interval * 1000), update)

        update()
        root.mainloop()

    return start_thread(_run)


def log_sensors(
    stop_event,
    writer,
    fh,
    lc1,
    lc2,
    lc3,
    ps1,
    ps2,
    ps3,
    valve_bank,
    interval=0.1,
):
    """Poll sensors and write readings to ``writer`` until ``stop_event`` is set.

    The ``csv.writer`` object itself does not expose a ``flush`` method, so the
    underlying file handle ``fh`` is also passed in and flushed after each row is
    written. This ensures data is written to disk even if the test is
    interrupted.
    """
    while not stop_event.is_set():
        ts = datetime.now().isoformat(sep=" ", timespec="milliseconds")
        try:
            row = [
                ts,
                f"{lc1._get_force_value('N'):.3f}",
                f"{lc2._get_force_value('N'):.3f}",
                f"{lc3._get_force_value('N'):.3f}",
                f"{ps1.read_position():.2f}",
                f"{ps2.read_position():.2f}",
                f"{ps3.read_position():.2f}",
                ",".join(sorted(valve_bank.active_valves)) or "-",
            ]
        except Exception:
            row = [ts] + ["err"] * 6 + ["-"]

        with event_lock:
            global event_message
            msg = event_message
            # Reset after reading so event only logged once
            if event_message:
                event_message = ""

        row.append(msg or "-")
        writer.writerow(row)
        fh.flush()
        time.sleep(interval)


# ------------------------------- Main -------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run valve test sequence")
    parser.add_argument("--ip", default="192.168.1.250", help="IO master IP address")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port")
    parser.add_argument("--log", default="test_log.csv", help="CSV file to write")
    args = parser.parse_args()

    master = IO_master(args.ip, SERVER_PORT=args.port)

    # AL1342 devices
    valve_bank = ValveBank(master, port_number=3)
    itv1 = PressureRegulatorITV1050(master, port_number=2)
    itv2 = PressureRegulatorITV1050(master, port_number=4)
    itv3 = PressureRegulatorITV1050(master, port_number=6)
    hub = AL2205Hub(master, port_number=1)

    # AL2205 devices
    ps1 = PositionSensorSDATMHS_M160(hub, x1_index=2)
    lc1 = LoadCellLCM300(hub, x1_index=3)
    ps2 = PositionSensorSDATMHS_M160(hub, x1_index=4)
    lc2 = LoadCellLCM300(hub, x1_index=5)
    ps3 = PositionSensorSDATMHS_M160(hub, x1_index=6)
    lc3 = LoadCellLCM300(hub, x1_index=7)

    # Configure regulators
    itv1.set_pressure(80)
    itv2.set_pressure(90)
    itv3.set_pressure(32)

    stop_event = threading.Event()
    with open(args.log, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "timestamp",
            "load_cell_1_N",
            "load_cell_2_N",
            "load_cell_3_N",
            "position_1_mm",
            "position_2_mm",
            "position_3_mm",
            "active_valves",
            "event",
        ])

        log_thread = start_thread(
            log_sensors,
            stop_event,
            writer,
            fh,
            lc1,
            lc2,
            lc3,
            ps1,
            ps2,
            ps3,
            valve_bank,
        )
        monitor_thread = start_loadcell_monitor(stop_event, lc1, lc2, lc3)

        try:
            # -------------------- Test Sequence --------------------
            valve_bank.valve_on("4.B", duration=1)
            Hold(2)  # 1s ON + 1s break

            valve_bank.valve_on("1.A", duration=1)
            Hold(2)

            valve_bank.valve_on("2.A")  # indefinite
            Hold(1)

            valve_bank.valve_on("3.B",1)
            Hold(1)

            valve_bank.valve_on("3.A", duration=2)
            record_event("Pull")
            Hold(2)
            record_event("Pull Stop")
            Hold(2.25)

            valve_bank.valve_on("4.A", duration=2)
            record_event("Push")
            Hold(2)
            record_event("Push Stop")
            Hold(2.25)

            valve_bank.all_off()
            Hold(1)

            valve_bank.valve_on("1.B", duration=1)
            Hold(1)
            Hold(1.1)
        finally:
            stop_event.set()
            log_thread.join()
            monitor_thread.join()
            valve_bank.all_off()
            master.close_client()

if __name__ == "__main__":
    main()
