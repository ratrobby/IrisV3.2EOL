from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300
import atexit

# Configure IO master and AL2205 hub
io = IO_master("192.168.1.1")
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


def Open_Monitor(duration=None):
    """Open a popup window that monitors all five load cells.

    Parameters
    ----------
    duration : float or None
        If provided, close the window automatically after ``duration`` seconds.
        ``None`` keeps the window open until the user closes it.
    """
    try:
        import tkinter as tk
        from threading import Thread
    except Exception as exc:  # pragma: no cover - environment specific
        print(f"Unable to import GUI modules: {exc}")
        return

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment specific
        print(f"Unable to open monitor window: {exc}")
        return

    root.title("Load Cell Monitor")
    labels = []
    for i in range(len(cells)):
        lbl = tk.Label(root, text=f"LC{i+1}: --")
        lbl.pack()
        labels.append(lbl)

    def _start_monitor(idx: int) -> None:
        def _update(value):
            if value is None:
                text = f"LC{idx+1}: N/A"
            else:
                text = f"LC{idx+1}: {value:.2f} N"
            labels[idx].config(text=text)

        Thread(target=cells[idx].monitor_force, kwargs={"callback": _update}, daemon=True).start()

    for i in range(len(cells)):
        _start_monitor(i)

    if duration is not None:
        root.after(int(duration * 1000), root.destroy)
    root.mainloop()
