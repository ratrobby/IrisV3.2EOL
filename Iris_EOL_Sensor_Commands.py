from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300
from PressureSensor_PQ3834 import PressureSensorPQ3834
import atexit
import threading
import tkinter as tk

# Configure IO master and AL2205 hub
io = IO_master("192.168.1.250")
try:
    io.prime(addr=1008, count=1)
except Exception:
    pass
hub = AL2205Hub(io, port_number=1)

# Instantiate five load cells on ports X1.0 to X1.4
cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]

# Instantiate pressure sensor on port X1.5
pressure_sensor = PressureSensorPQ3834(hub, x1_index=5)

# Ensure Modbus client is closed on exit
atexit.register(io.close_client)


def readLC(n):
    """Print the force from load cell ``n`` in newtons.

    Parameters
    ----------
    n : int
        Load cell number (1-5).
    """
    if not 1 <= n <= len(cells):
        raise ValueError("Load cell number must be between 1 and 5")
    force = cells[n - 1].read_force()
    if force is None:
        print(f"LC{n}: N/A")
    else:
        print(f"LC{n}: {force:.2f} N")


def readPS():
    """Print the pressure reading from the PQ3834 sensor in PSI."""
    pressure = pressure_sensor.read_pressure()
    if pressure is None:
        print("PS: N/A")
    else:
        print(f"PS: {pressure:.2f} PSI")


def Open_Monitor():
    """Open a window that continually displays force and pressure readings."""

    window = tk.Tk()
    window.title("Sensor Monitor")

    labels = []
    stop_events = []

    for i in range(len(cells)):
        var = tk.StringVar(value=f"LC{i + 1}: --- N")
        label = tk.Label(window, textvariable=var)
        label.pack()
        labels.append(var)

        stop_event = threading.Event()
        stop_events.append(stop_event)

        def make_callback(idx):
            def _update(force):
                if force is None:
                    labels[idx].set(f"LC{idx + 1}: N/A")
                else:
                    labels[idx].set(f"LC{idx + 1}: {force:.2f} N")
            return _update

        thread = threading.Thread(
            target=cells[i].monitor_force,
            kwargs={"callback": make_callback(i), "stop_event": stop_event},
            daemon=True,
        )
        thread.start()

    # Add pressure sensor label and thread
    pressure_var = tk.StringVar(value="PS: --- PSI")
    pressure_label = tk.Label(window, textvariable=pressure_var)
    pressure_label.pack()

    pressure_stop = threading.Event()
    stop_events.append(pressure_stop)

    def pressure_callback(value):
        if value is None:
            pressure_var.set("PS: N/A")
        else:
            pressure_var.set(f"PS: {value:.2f} PSI")

    pressure_thread = threading.Thread(
        target=pressure_sensor.monitor_pressure,
        kwargs={"callback": pressure_callback, "stop_event": pressure_stop},
        daemon=True,
    )
    pressure_thread.start()

    def on_close():
        for ev in stop_events:
            ev.set()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_close)
    window.mainloop()
