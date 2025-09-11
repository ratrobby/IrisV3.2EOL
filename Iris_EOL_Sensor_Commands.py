from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300
from PressureSensor_PQ3834 import PressureSensorPQ3834
from FlowPressure_SD9500 import FlowPressureSensorSD9500
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

# Instantiate SD9500 flow/pressure sensor on port X02
sd9500_sensor = FlowPressureSensorSD9500(io, port_number=2)

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


def readVF():
    """Print the flow reading from the SD9500 sensor in CFM."""
    flow = sd9500_sensor.readVF()
    if flow is None:
        print("VF: N/A")
    else:
        print(f"VF: {flow:.2f} CFM")


def readVP():
    """Print the pressure reading from the SD9500 sensor in PSI."""
    pressure = sd9500_sensor.readVP()
    if pressure is None:
        print("VP: N/A")
    else:
        print(f"VP: {pressure:.2f} PSI")


def open_monitor():
    """Open a small window that continually displays force and pressure readings.

    The window geometry is set to roughly one fifth of the user's screen size
    so it can be left running unobtrusively while still showing live values for
    all five load cells and the pressure sensor.
    """

    window = tk.Tk()
    window.title("Sensor Monitor")

    # Resize the window to approximately one fifth of the screen dimensions.
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    width = max(200, screen_width // 5)
    height = max(200, screen_height // 5)
    window.geometry(f"{width}x{height}")

    # Configure grid so that the name column uses roughly two thirds of the
    # window width while the value column uses the remaining third. Each row is
    # given equal weight so that the six labels are distributed evenly across
    # the window height.
    window.columnconfigure(0, weight=2)
    window.columnconfigure(1, weight=1)
    for i in range(len(cells) + 1):
        window.rowconfigure(i, weight=1)

    font = ("TkDefaultFont", 16)

    value_vars = []
    stop_events = []

    for i in range(len(cells)):
        name_label = tk.Label(window, text=f"LC{i + 1}", font=font, anchor="center")
        name_label.grid(row=i, column=0, sticky="nsew", padx=5, pady=5)

        var = tk.StringVar(value="--- N")
        value_label = tk.Label(window, textvariable=var, font=font, anchor="center")
        value_label.grid(row=i, column=1, sticky="nsew", padx=5, pady=5)
        value_vars.append(var)

        stop_event = threading.Event()
        stop_events.append(stop_event)

        def make_callback(idx):
            def _update(force):
                if force is None:
                    value_vars[idx].set("N/A")
                else:
                    value_vars[idx].set(f"{force:.2f} N")
            return _update

        thread = threading.Thread(
            target=cells[i].monitor_force,
            kwargs={"callback": make_callback(i), "stop_event": stop_event},
            daemon=True,
        )
        thread.start()

    # Add pressure sensor label and thread
    pressure_name = tk.Label(window, text="PS", font=font, anchor="center")
    pressure_name.grid(row=len(cells), column=0, sticky="nsew", padx=5, pady=5)

    pressure_var = tk.StringVar(value="--- PSI")
    pressure_value = tk.Label(window, textvariable=pressure_var, font=font, anchor="center")
    pressure_value.grid(row=len(cells), column=1, sticky="nsew", padx=5, pady=5)

    pressure_stop = threading.Event()
    stop_events.append(pressure_stop)

    def pressure_callback(value):
        if value is None:
            pressure_var.set("N/A")
        else:
            pressure_var.set(f"{value:.2f} PSI")

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


# Backwards compatibility for previous name.
Open_Monitor = open_monitor
