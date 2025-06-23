"""
    =======================================
    PositionSensor Class - Public Interface
    =======================================

    Purpose:
    --------
    Read and interpret a linear position sensor connected to AL2205 analog input.

    Constructor:
    ------------
    PositionSensor(al2205, x1_index, stroke_mm=150)

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

# Public API decorator
def class_api(func):
    func._is_class_api = True
    return func

from decorators import test_setup, test_command, device_class


@device_class
class PositionSensor:

    @classmethod
    def instructions(cls):
        return """
    Command: ~read_position_mm()~
        Use: Reads current position of cylinder in mm
        Inputs:
            - none

                """

    CALIBRATION_FILE = "sensor_calibrations.json"

    def __init__(self, al2205, x1_index, stroke_mm=150):
        self.al2205 = al2205
        self.x1_index = x1_index
        self.stroke_mm = stroke_mm
        self.calibration_data = self._load_calibration()

    @test_setup
    def calibrate_min(self):
        """
        Save current raw value as the 0mm calibration point.
        """
        raw_value = self.al2205.read_index(self.x1_index)
        self._save_calibration_value("min", raw_value)
        print(f"✅ Calibrated MIN for X1.{self.x1_index}: {raw_value}")

    @test_setup
    def calibrate_max(self):
        """
        Save current raw value as the max (stroke_mm) calibration point.
        """
        raw_value = self.al2205.read_index(self.x1_index)
        self._save_calibration_value("max", raw_value)
        print(f"✅ Calibrated MAX for X1.{self.x1_index}: {raw_value}")

    @test_command
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
