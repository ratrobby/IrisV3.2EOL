"""
    =======================================
    PositionSensorSDATMHS_M160 - Public Interface
    =======================================

    Purpose:
    --------
    Read and interpret a linear position sensor connected to AL2205 analog input.

    Constructor:
    ------------
    PositionSensorSDATMHS_M160(al2205, x1_index, stroke_mm=150)

    Public Methods:
    ---------------
    - calibrate_min(): Save current raw reading as 0mm.
    - calibrate_max(): Save current raw reading as full stroke (e.g., 150mm).
    - read_position(): Return live position in mm.
    - monitor_position(duration=None): Continuously print position every 0.25s.

    Notes:
    ------
    - Calibration values are saved to the file given by the
      ``MRLF_CALIBRATION_FILE`` environment variable. If the variable is not
      set, ``config/sensor_calibrations.json`` in the repository root is used.
    - X1_index corresponds to analog input channel (0, 1, 2, ...).
    """

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util
import sys
import datetime
import time
from thread_utils import start_thread

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Path to the repository root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Public API decorator
def class_api(func):
    func._is_class_api = True
    return func

from decorators import setup_command, test_command, device_class


@device_class
class PositionSensorSDATMHS_M160:

    @classmethod
    def setup_instructions(cls):
        return [
            {
                "title": "Calibrate_PosSensor_PSG()",
                "content": (
                    "Use: Launch PySimpleGUI tool to calibrate all mapped position sensors"
                ),
            }
        ]
    @classmethod
    def test_instructions(cls):
        return [
            {
                "title": "read_position()",
                "content": (
                    "Use: Reads current position of cylinder in mm\n"
                    "Inputs:\n"
                    "    - none"
                ),
            },
            {
                "title": "monitor_position(duration=None)",
                "content": (
                    "Use: Continuously prints position until stopped\n"
                    "Inputs:\n"
                    "    - duration: Total monitor time in seconds (None runs until interrupted)\n"
                    "Example:\n"
                    "    - monitor_position(3) - Print position every 0.25 s for 3 seconds"
                ),
            }
        ]

    @classmethod
    def calibration_steps(cls):
        """Return step definitions for the generic calibration wizard."""
        return [
            {
                "prompt": (
                    "Move sensor to fully retracted position then capture the minimum"
                ),
                "action": "calibrate_min",
                "button": "Capture Min",
            },
            {
                "prompt": (
                    "Move sensor to fully extended position then capture the maximum"
                ),
                "action": "calibrate_max",
                "button": "Capture Max",
            },
            {
                "prompt": "Enter stroke length in mm and save",
                "action": "set_stroke_length",
                "input": "stroke_mm",
                "button": "Save Stroke",
            },
        ]

    CALIBRATION_FILE = os.path.expanduser(
        os.environ.get(
            "MRLF_CALIBRATION_FILE",
            os.path.join(REPO_ROOT, "config", "sensor_calibrations.json"),
        )
    )

    def __init__(self, al2205, x1_index, stroke_mm=150):
        self.al2205 = al2205
        self.x1_index = x1_index
        self.stroke_mm = stroke_mm
        self.calibration_data = self._load_calibration()
        if "stroke" in self.calibration_data:
            self.stroke_mm = self.calibration_data["stroke"]

    def calibrate_min(self):
        """
        Save current raw value as the 0mm calibration point.
        """
        raw_value = self.al2205.read_index(self.x1_index)
        self._save_calibration_value("min", raw_value)
        print(f"✅ Calibrated MIN for X1.{self.x1_index}: {raw_value}")
        return raw_value

    def calibrate_max(self):
        """
        Save current raw value as the max (stroke_mm) calibration point.
        """
        raw_value = self.al2205.read_index(self.x1_index)
        self._save_calibration_value("max", raw_value)
        print(f"✅ Calibrated MAX for X1.{self.x1_index}: {raw_value}")
        return raw_value

    def read_position(self):
        """
        Return live position in millimeters, clamped between 0 and stroke.
        """
        raw = self.al2205.read_index(self.x1_index)
        min_val = self.calibration_data.get("min")
        max_val = self.calibration_data.get("max")

        if min_val is None or max_val is None:
            raise RuntimeError(f"⚠️ Sensor X1.{self.x1_index} is not calibrated yet.")

        span = max_val - min_val
        if span == 0:
            raise ZeroDivisionError("Calibration min and max are equal.")

        position = ((raw - min_val) / span) * self.stroke_mm
        result = round(max(0.0, min(position, self.stroke_mm)), 2)
        if hasattr(self, "_logger_alias"):
            from logger import record_value

            record_value(self._logger_alias, f"{result:.2f}")
        return result

    def read_position_thread(self):
        """Run :meth:`read_position` in a background thread."""
        return start_thread(self.read_position)

    def monitor_position(self, duration=None):
        """Continuously print position readings.

        Parameters
        ----------
        duration : float or None, optional
            Total time in seconds to run the monitor. ``None`` runs until
            interrupted.

        Notes
        -----
        The reading interval is fixed at ``0.25`` seconds.
        """
        interval = 0.25
        start = time.time()
        try:
            while True:
                pos = self.read_position()
                print(f"Position = {pos:.2f} mm")
                if hasattr(self, "_logger_alias"):
                    from logger import record_value

                    record_value(self._logger_alias, f"{pos:.2f}")
                if duration is not None and (time.time() - start) >= duration:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Stopped position monitoring")
        finally:
            if duration is not None:
                print("Position monitoring complete")

    def monitor_position_thread(self, duration=None):
        """Run :meth:`monitor_position` in a background thread."""
        return start_thread(self.monitor_position, duration=duration)

    def set_stroke_length(self, length_mm):
        """Persist and apply a new stroke length for this sensor."""
        self.stroke_mm = float(length_mm)
        self._save_calibration_value("stroke", self.stroke_mm)
        print(f"✅ Set stroke length for X1.{self.x1_index}: {self.stroke_mm} mm")

    # ---------------------- GUI Integration ----------------------
    def setup_widget(self, parent, name=None):
        """Return a Tkinter frame with calibration controls."""
        frame = ttk.Frame(parent)
        label = ttk.Label(
            frame,
            text=name or f"Sensor X1.{self.x1_index}",
            font=("Arial", 10, "bold underline"),
        )
        label.grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Label(frame, text="Min").grid(row=1, column=0)
        ttk.Button(frame, text="Capture",
                   command=self._capture_min).grid(row=2, column=0, padx=2)

        ttk.Label(frame, text="Max").grid(row=1, column=1)
        ttk.Button(frame, text="Capture",
                   command=self._capture_max).grid(row=2, column=1, padx=2)

        ttk.Label(frame, text="Stroke").grid(row=1, column=2)
        stroke_var = tk.StringVar(value=str(self.stroke_mm))
        entry = ttk.Entry(frame, textvariable=stroke_var, width=6)
        entry.grid(row=2, column=2, padx=2)
        ttk.Button(frame, text="Capture",
                   command=lambda: self._capture_stroke(stroke_var)).grid(
            row=2, column=3, padx=2)

        return frame

    def _capture_min(self):
        value = self.calibrate_min()
        _log(f"X1.{self.x1_index} MIN: {value}")

    def _capture_max(self):
        value = self.calibrate_max()
        _log(f"X1.{self.x1_index} MAX: {value}")

    def _capture_stroke(self, var):
        try:
            length = float(var.get())
        except ValueError:
            messagebox.showerror("Input Error", "Invalid stroke length")
            return
        self.set_stroke_length(length)
        _log(f"X1.{self.x1_index} STROKE: {length}")

    # ---------- Internal-only ----------

    def _load_calibration(self):
        os.makedirs(os.path.dirname(self.CALIBRATION_FILE), exist_ok=True)
        if os.path.exists(self.CALIBRATION_FILE):
            with open(self.CALIBRATION_FILE, "r") as f:
                all_data = json.load(f)
                return all_data.get(f"X1.{self.x1_index}", {})
        return {}

    def _save_calibration_value(self, key, value):
        data = {}
        if os.path.exists(self.CALIBRATION_FILE):
            with open(self.CALIBRATION_FILE, "r") as f:
                data = json.load(f)

        sensor_key = f"X1.{self.x1_index}"
        if sensor_key not in data:
            data[sensor_key] = {}

        data[sensor_key][key] = value

        os.makedirs(os.path.dirname(self.CALIBRATION_FILE), exist_ok=True)
        with open(self.CALIBRATION_FILE, "w") as f:
            json.dump(data, f, indent=4)

        self.calibration_data[key] = value


# ==================== Calibration Wizard Integration ====================
LOG_FILE = os.path.join(REPO_ROOT, "logs", "position_sensor_calibration.log")


def _log(message):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} - {message}\n")


def _load_position_sensors():
    script = os.environ.get("MRLF_TEST_SCRIPT")
    if not script or not os.path.exists(script):
        return []
    spec = importlib.util.spec_from_file_location("user_devices", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sensors = []
    for name, obj in module.__dict__.items():
        if isinstance(obj, PositionSensorSDATMHS_M160):
            port = f"X1.{obj.x1_index}"
            sensors.append((obj, name, port))
    return sensors


_wizard_win = None


class CalibrationWizard:
    def __init__(self, sensors):
        global _wizard_win
        if _wizard_win and _wizard_win.winfo_exists():
            _wizard_win.lift()
            return

        self.sensors = sensors  # list of (sensor, name, port)
        self.current_step = 0
        self.entries = []

        self.win = tk.Toplevel()
        self.win.title("Position Sensor Calibration")
        _wizard_win = self.win

        self.label = ttk.Label(self.win, text="", font=("Arial", 12), wraplength=380)
        self.label.pack(pady=10)

        self.body = ttk.Frame(self.win)
        self.body.pack(pady=5)

        self.button = ttk.Button(self.win, text="", command=self.next_step)
        self.button.pack(pady=10)

        self.steps = [
            ("Move sensors to fully retracted position then calibrate each", "Next", None),
            ("Move sensors to fully extended position then calibrate each", "Next", None),
            ("Enter stroke length for each cylinder", "Save Strokes", self.save_strokes),
            ("✅ Sensors Calibrated!", "Close", self.finish),
        ]

        self.show_step()

    def clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def show_step(self):
        self.clear_body()
        if self.current_step >= len(self.steps):
            return
        msg, btn_text, _ = self.steps[self.current_step]
        self.label.config(text=msg)
        self.button.config(text=btn_text)
        if self.current_step == 0:
            for sensor, name, port in self.sensors:
                frame = ttk.Frame(self.body)
                frame.pack(pady=2)
                ttk.Label(frame, text=f"{name} ({port})").pack(side="left")
                ttk.Button(frame, text="Calibrate Min", command=lambda s=sensor, n=name, p=port: self._cal_min(s, n, p)).pack(side="left", padx=5)
        elif self.current_step == 1:
            for sensor, name, port in self.sensors:
                frame = ttk.Frame(self.body)
                frame.pack(pady=2)
                ttk.Label(frame, text=f"{name} ({port})").pack(side="left")
                ttk.Button(frame, text="Calibrate Max", command=lambda s=sensor, n=name, p=port: self._cal_max(s, n, p)).pack(side="left", padx=5)
        elif self.current_step == 2:
            self.entries = []
            for sensor, name, port in self.sensors:
                frame = ttk.Frame(self.body)
                frame.pack(pady=2)
                ttk.Label(frame, text=f"{name} ({port})").pack(side="left")
                entry = ttk.Entry(frame, width=8)
                entry.insert(0, str(sensor.stroke_mm))
                entry.pack(side="left", padx=5)
                self.entries.append((sensor, name, port, entry))

    def next_step(self):
        _, _, action = self.steps[self.current_step]
        if callable(action):
            action()
        self.current_step += 1
        self.show_step()

    def _cal_min(self, sensor, name, port):
        value = sensor.calibrate_min()
        _log(f"{name} {port} MIN: {value}")

    def _cal_max(self, sensor, name, port):
        value = sensor.calibrate_max()
        _log(f"{name} {port} MAX: {value}")

    def save_strokes(self):
        for sensor, name, port, entry in self.entries:
            try:
                length = float(entry.get())
            except ValueError:
                messagebox.showerror("Input Error", f"Invalid stroke for {name}")
                return
            sensor.set_stroke_length(length)
            _log(f"{name} {port} STROKE: {length}")

    def finish(self):
        global _wizard_win
        _wizard_win = None
        self.win.destroy()

def Calibrate_PosSensor():
    """Launch the calibration wizard for all mapped position sensors."""
    if "MRLF_TEST_SCRIPT" not in os.environ:
        messagebox.showwarning(
            "MRLF_TEST_SCRIPT Missing",
            "MRLF_TEST_SCRIPT environment variable not set. Using default configuration."
        )
    sensors = _load_position_sensors()
    if not sensors:
        messagebox.showinfo("No Sensors",
                            "No position sensors mapped to this test.")
        return
    CalibrationWizard(sensors)

