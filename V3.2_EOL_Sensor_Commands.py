from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300
import atexit
import threading
import tkinter as tk

# Configure IO master and AL2205 hub
io = IO_master("192.168.1.1")
try:
    io.prime(addr=1008, count=1)
except Exception:
    pass
hub = AL2205Hub(io, port_number=1)

# Instantiate five load cells on ports X1.0 to X1.4
cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]

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


def Open_Monitor():
    """Open a window that continually displays force readings for all load cells."""

    window = tk.Tk()
    window.title("Load Cell Monitor")

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

    def on_close():
        for ev in stop_events:
            ev.set()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_close)
    window.mainloop()
