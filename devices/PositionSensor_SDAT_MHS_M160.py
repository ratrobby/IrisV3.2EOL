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
    - read_position_mm(): Return live position in mm.

    Notes:
    ------
    - Calibration values are saved in 'sensor_calibrations.json'.
    - X1_index corresponds to analog input channel (0, 1, 2, ...).
    """

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util
import sys
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

    CALIBRATION_FILE = "sensor_calibrations.json"

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
        return round(max(0.0, min(position, self.stroke_mm)), 2)

    def set_stroke_length(self, length_mm):
        """Persist and apply a new stroke length for this sensor."""
        self.stroke_mm = float(length_mm)
        self._save_calibration_value("stroke", self.stroke_mm)
        print(f"✅ Set stroke length for X1.{self.x1_index}: {self.stroke_mm} mm")

    # ---------------------- GUI Integration ----------------------
    def setup_widget(self, parent, name=None):
        """Return a Tkinter frame with calibration controls."""
        frame = ttk.Frame(parent)
        label = ttk.Label(frame, text=name or f"Sensor X1.{self.x1_index}")
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

        with open(self.CALIBRATION_FILE, "w") as f:
            json.dump(data, f, indent=4)

        self.calibration_data[key] = value


# ==================== Calibration Wizard Integration ====================

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_CELL_FILE = os.path.join(REPO_ROOT, "config", "Test_Cell_1_Devices.py")
LOG_FILE = os.path.join(REPO_ROOT, "logs", "position_sensor_calibration.log")


def _log(message):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} - {message}\n")


def _load_position_sensors():
    if not os.path.exists(TEST_CELL_FILE):
        return []
    spec = importlib.util.spec_from_file_location("Test_Cell_1_Devices",
                                                TEST_CELL_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["Test_Cell_1_Devices"] = module
    spec.loader.exec_module(module)

    sensors = []
    for name, obj in module.__dict__.items():
        if isinstance(obj, PositionSensorSDATMHS_M160):
            port = f"X1.{obj.x1_index}"
            sensors.append((obj, name, port))
    return sensors


class CalibrationWizard:
    def __init__(self, sensors):
        self.sensors = sensors  # list of (sensor, name, port)
        self.current_step = 0
        self.entries = []

        self.win = tk.Toplevel()
        self.win.title("Position Sensor Calibration")

        self.label = ttk.Label(self.win, text="", font=("Arial", 12),
                               wraplength=380)
        self.label.pack(pady=10)

        self.body = ttk.Frame(self.win)
        self.body.pack(pady=5)

        self.button = ttk.Button(self.win, text="", command=self.next_step)
        self.button.pack(pady=10)

        self.steps = [
            ("Move all position sensors to fully retracted position",
             "Calibrate Min", self.calibrate_min),
            ("Move all position sensors to their fully extended position",
             "Calibrate Max", self.calibrate_max),
            ("Enter stroke length for each cylinder",
             "Save Strokes", self.save_strokes),
            ("✅ Sensors Calibrated!", "Close", self.win.destroy),
        ]

        self.show_step()

    def clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def show_step(self):
        self.clear_body()
        if self.current_step < len(self.steps):
            msg, btn_text, _ = self.steps[self.current_step]
            self.label.config(text=msg)
            self.button.config(text=btn_text)
            if self.current_step == 2:
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
        action()
        self.current_step += 1
        self.show_step()

    def calibrate_min(self):
        for sensor, name, port in self.sensors:
            value = sensor.calibrate_min()
            _log(f"{name} {port} MIN: {value}")

    def calibrate_max(self):
        for sensor, name, port in self.sensors:
            value = sensor.calibrate_max()
            _log(f"{name} {port} MAX: {value}")

    def save_strokes(self):
        for sensor, name, port, entry in self.entries:
            try:
                length = float(entry.get())
            except ValueError:
                messagebox.showerror("Input Error",
                                     f"Invalid stroke for {name}")
                return
            sensor.set_stroke_length(length)
            _log(f"{name} {port} STROKE: {length}")

def Calibrate_PosSensor():
    """Launch the calibration wizard for all mapped position sensors."""
    sensors = _load_position_sensors()
    if not sensors:
        messagebox.showinfo("No Sensors",
                            "No position sensors mapped to Test Cell 1.")
        return
    CalibrationWizard(sensors)

