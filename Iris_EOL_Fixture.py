from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300
from PressureSensor_PQ3834 import PressureSensorPQ3834
from FlowPressure_SD9500 import FlowPressureSensorSD9500
from FlowSensor_SD6020 import FlowSensorSD6020
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

# Instantiate SD6020 flow sensor on port X03
sd6020_sensor = FlowSensorSD6020(io, port_number=3)

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


def readPF():
    """Print the flow reading from the SD6020 sensor in CFM."""
    flow = sd6020_sensor.readPF()
    if flow is None:
        print("PF: N/A")
    else:
        print(f"PF: {flow:.2f} CFM")


def open_monitor():
    """Open a small window that continually displays sensor readings.

    The window geometry is set to roughly one fifth of the user's screen size
    so it can be left running unobtrusively while still showing live values for
    all five load cells, the PQ3834 pressure sensor, the SD9500 flow/pressure
    sensor, and the SD6020 flow sensor.
    """

    window = tk.Tk()
    window.title("Sensor Monitor")

    # Resize the window to approximately one fifth of the screen dimensions.
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    width = max(200, screen_width // 5)
    height = max(200, screen_height // 5)
    window.geometry(f"{width}x{height}")

    # Configure grid so that each row uses equal height. Individual frames will
    # manage the two column layout internally to maintain the 2:1 width ratio
    # between sensor names and values.
    window.columnconfigure(0, weight=1)
    for i in range(len(cells) + 4):
        window.rowconfigure(i, weight=1)

    font = ("TkDefaultFont", 16)

    value_vars = []
    stop_events = []

    for i in range(len(cells)):
        # Create a frame for each load cell row to draw a visible border
        row_frame = tk.Frame(window, bd=1, relief="solid")
        row_frame.grid(row=i, column=0, sticky="nsew", padx=5, pady=5)
        row_frame.columnconfigure(0, weight=2)
        row_frame.columnconfigure(1, weight=1)

        name_label = tk.Label(row_frame, text=f"LC{i + 1}", font=font, anchor="center")
        name_label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        var = tk.StringVar(value="--- N")
        value_label = tk.Label(row_frame, textvariable=var, font=font, anchor="center")
        value_label.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
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

    # Add pressure sensor row with a frame and thread
    pressure_frame = tk.Frame(window, bd=1, relief="solid")
    pressure_frame.grid(row=len(cells), column=0, sticky="nsew", padx=5, pady=5)
    pressure_frame.columnconfigure(0, weight=2)
    pressure_frame.columnconfigure(1, weight=1)

    pressure_name = tk.Label(pressure_frame, text="PS", font=font, anchor="center")
    pressure_name.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    pressure_var = tk.StringVar(value="--- PSI")
    pressure_value = tk.Label(pressure_frame, textvariable=pressure_var, font=font, anchor="center")
    pressure_value.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

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

    # Add SD9500 flow and pressure rows with a single thread updating both
    flow_frame = tk.Frame(window, bd=1, relief="solid")
    flow_frame.grid(row=len(cells) + 1, column=0, sticky="nsew", padx=5, pady=5)
    flow_frame.columnconfigure(0, weight=2)
    flow_frame.columnconfigure(1, weight=1)

    flow_name = tk.Label(flow_frame, text="VF", font=font, anchor="center")
    flow_name.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    flow_var = tk.StringVar(value="--- CFM")
    flow_value = tk.Label(flow_frame, textvariable=flow_var, font=font, anchor="center")
    flow_value.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

    sd_pressure_frame = tk.Frame(window, bd=1, relief="solid")
    sd_pressure_frame.grid(row=len(cells) + 2, column=0, sticky="nsew", padx=5, pady=5)
    sd_pressure_frame.columnconfigure(0, weight=2)
    sd_pressure_frame.columnconfigure(1, weight=1)

    sd_pressure_name = tk.Label(sd_pressure_frame, text="VP", font=font, anchor="center")
    sd_pressure_name.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    sd_pressure_var = tk.StringVar(value="--- PSI")
    sd_pressure_value = tk.Label(sd_pressure_frame, textvariable=sd_pressure_var, font=font, anchor="center")
    sd_pressure_value.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

    sd_stop = threading.Event()
    stop_events.append(sd_stop)

    def sd_callback(flow, pressure):
        if flow is None:
            flow_var.set("N/A")
        else:
            flow_var.set(f"{flow:.2f} CFM")
        if pressure is None:
            sd_pressure_var.set("N/A")
        else:
            sd_pressure_var.set(f"{pressure:.2f} PSI")

    sd_thread = threading.Thread(
        target=sd9500_sensor.monitor,
        kwargs={"callback": sd_callback, "stop_event": sd_stop},
        daemon=True,
    )
    sd_thread.start()

    # Add SD6020 flow row with its own thread
    pf_frame = tk.Frame(window, bd=1, relief="solid")
    pf_frame.grid(row=len(cells) + 3, column=0, sticky="nsew", padx=5, pady=5)
    pf_frame.columnconfigure(0, weight=2)
    pf_frame.columnconfigure(1, weight=1)

    pf_name = tk.Label(pf_frame, text="PF", font=font, anchor="center")
    pf_name.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    pf_var = tk.StringVar(value="--- CFM")
    pf_value = tk.Label(pf_frame, textvariable=pf_var, font=font, anchor="center")
    pf_value.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

    pf_stop = threading.Event()
    stop_events.append(pf_stop)

    def pf_callback(flow):
        if flow is None:
            pf_var.set("N/A")
        else:
            pf_var.set(f"{flow:.2f} CFM")

    pf_thread = threading.Thread(
        target=sd6020_sensor.monitor,
        kwargs={"callback": pf_callback, "stop_event": pf_stop},
        daemon=True,
    )
    pf_thread.start()

    def on_close():
        for ev in stop_events:
            ev.set()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_close)
    window.mainloop()

    if __name__ == "__main__":
        readPS()


# Backwards compatibility for previous name.
Open_Monitor = open_monitor
