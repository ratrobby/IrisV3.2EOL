import os
import sys
import time

# Allow importing project modules when executed directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decorators import device_class
import importlib.util
import tkinter as tk
from tkinter import messagebox, ttk
"""
    =====================================
    LoadCellLCM300 - Public Interface
    =====================================

    Purpose:
    --------
    Read data from a load cell connected to an AL2205 analog input.

    Constructor:
    ------------
    LoadCellLCM300(al2205_instance, x1_index)

    Public Methods:
    ---------------
    - read_force(unit="lbf"): Return a single force reading.
    - monitor_force(unit="lbf", interval=0.5): Continuously print force readings.
    - monitor_force_window(interval=0.2): Show live force in both lbf and N.

    Notes:
    ------
    - X1 index maps to AL2205 analog input ports (X1.0 to X1.7).
    - Uses example calibration: 5V = 0 lbf, 0V = 50 lbf (10 lbf/V).
"""

@device_class
class LoadCellLCM300:

    @classmethod
    def test_instructions(cls):
        return [
            {
                "title": "read_force(unit)",
                "content": (
                    "Use: Returns a single force reading in pounds-force or newtons\n"
                    "Inputs:\n"
                    "  - unit: Defines the unit of force the reading will be in\n"
                    "          - lbf: pounds-force\n"
                    "          - N: Newtons\n"
                    "Example:\n"
                    "  - read_force(\"N\") - Reads force in newtons\n"
                    "  - read_force(\"lbf\") - Reads force in pounds-force"
                ),
            },
            {
                "title": "monitor_force(unit, interval)",
                "content": (
                    "Use: Continuously prints force readings until stopped\n"
                    "Inputs:\n"
                    "  - unit: Force units (lbf or N)\n"
                    "  - interval=: Time between readings in seconds (default 0.5)\n"
                    "Example:\n"
                    "  - monitor_force(\"lbf\", interval=1) - Print lbf every second"
                ),
            },
        ]

    @classmethod
    def setup_instructions(cls):
        return [
            {
                "title": "Calibrate_LoadCell_Zero()",
                "content": (
                    "Use: Opens a live monitor window to zero the load cell amplifier.\n"
                    "The window shows force in both lbf and N."
                ),
            }
        ]

    @classmethod
    def calibration_steps(cls):
        return [
            {
                "prompt": (
                    "Open a monitor window and adjust the amplifier's zero dial until the reading is 0.\n"
                    "The window displays force in both lbf and N."
                ),
                "action": "monitor_force_window",
                "button": "Open Monitor",
            },
            {
                "prompt": "Close the monitor window and click Finish",
                "button": "Finish",
            },
        ]

    def __init__(self, al2205_instance, x1_index):
        """
        Parameters:
        - al2205_instance: instance of AL2205
        - x1_index: channel index on the AL2205 (0–7 for X1.0–X1.7)
        """
        self.device = al2205_instance
        self.x1_index = x1_index


    def read_raw_data(self):
        """
        Return raw 16-bit value from AL2205 (unsigned, 0–65535).
        """
        return self.device.read_index(self.x1_index)


    def read_voltage(self):
        """
        Convert raw value to voltage (0–10 V).

        Returns:
        - Voltage as float (e.g., 0.0 to 10.0)
        """
        raw = self.read_raw_data()
        return raw / 1000 if raw is not None else None

    def _get_force_value(self, unit="lbf"):
        """Return the current force without printing."""
        voltage = self.read_voltage()
        if voltage is None:
            return None

        force_lbf = (5.0 - voltage) * 10.0

        unit = unit.lower()
        if unit == "lbf":
            return force_lbf
        if unit == "n":
            return force_lbf * 4.44822
        raise ValueError("Invalid unit. Use 'lbf' or 'n'.")

    def read_force(self, unit="lbf"):
        """Convert voltage to force and print the value."""
        result = self._get_force_value(unit)
        if result is None:
            return None
        unit_label = "lbf" if unit.lower() == "lbf" else "N"
        print(f"Force = {result:.2f}{unit_label}")
        return result

    def monitor_force(self, unit="lbf", interval=0.5):
        """Continuously print force readings until interrupted."""
        try:
            while True:
                self.read_force(unit=unit)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Stopped force monitoring")

    # ------------------------------------------------------------------
    def monitor_force_window(self, interval=0.2):
        """Open a small window showing the live force reading in lbf and N."""
        win = tk.Toplevel()
        win.title("Load Cell Monitor")

        label = ttk.Label(win, text="", font=("Arial", 12))
        label.pack(padx=10, pady=10)

        running = True

        def update():
            if not running:
                return
            lbf_val = self._get_force_value("lbf")
            n_val = self._get_force_value("n")
            if lbf_val is None or n_val is None:
                label.config(text="N/A")
            else:
                label.config(text=f"{lbf_val:.2f} lbf / {n_val:.2f} N")
            win.after(int(interval * 1000), update)

        def close():
            nonlocal running
            running = False
            win.destroy()

        ttk.Button(win, text="Close", command=close).pack(pady=5)
        win.protocol("WM_DELETE_WINDOW", close)

        update()


# ==================== Calibration Helper ====================
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_load_cells():
    script = os.environ.get("MRLF_TEST_SCRIPT")
    if not script or not os.path.exists(script):
        return []
    spec = importlib.util.spec_from_file_location("user_devices", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cells = []
    for name, obj in module.__dict__.items():
        if isinstance(obj, LoadCellLCM300):
            port = f"X1.{obj.x1_index}"
            cells.append((obj, name, port))
    return cells


_monitor_win = None

def Calibrate_LoadCell_Zero(interval=0.2):
    """Launch a single monitor window for all mapped load cells."""
    if "MRLF_TEST_SCRIPT" not in os.environ:
        messagebox.showwarning(
            "MRLF_TEST_SCRIPT Missing",
            "MRLF_TEST_SCRIPT environment variable not set. Using default configuration."
        )
    cells = _load_load_cells()
    if not cells:
        messagebox.showinfo("No Load Cells", "No LoadCell_LCM300 devices mapped to this test.")
        return

    global _monitor_win
    if _monitor_win and _monitor_win.winfo_exists():
        _monitor_win.lift()
        return

    win = tk.Toplevel()
    win.title("Load Cell Calibration")
    _monitor_win = win

    rows = []
    for cell, name, port in cells:
        frame = ttk.Frame(win)
        frame.pack(padx=5, pady=2)
        ttk.Label(frame, text=f"{name} ({port})").pack(side="left")
        var = tk.StringVar(value="0")
        ttk.Label(frame, textvariable=var).pack(side="left", padx=5)
        rows.append((cell, var))

    def update():
        if not _monitor_win or not _monitor_win.winfo_exists():
            return
        for cell, var in rows:
            lbf = cell._get_force_value("lbf")
            n = cell._get_force_value("n")
            if lbf is None or n is None:
                var.set("N/A")
            else:
                var.set(f"{lbf:.2f} lbf / {n:.2f} N")
        win.after(int(interval * 1000), update)

    def close():
        global _monitor_win
        _monitor_win = None
        win.destroy()

    ttk.Button(win, text="Close", command=close).pack(pady=5)
    win.protocol("WM_DELETE_WINDOW", close)
    update()
