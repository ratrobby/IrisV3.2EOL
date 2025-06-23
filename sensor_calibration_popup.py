import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util
import sys
import os

# -- Device Utilities --
class DeviceUtils:
    TEST_CELL_1_SCRIPT = r"C:\Users\ratrobby\Desktop\MRLF Repository\MRLF_Devices\Test_Cell_Device_Logs\Test_Cell_1_Devices.py"
    POSITION_SENSOR_CLASS = "PositionSensor"
    DEVICE_FILE = r"C:\Users\ratrobby\Desktop\MRLF Repository\MRLF_Devices\PositionSensor_SDAT_MHS_M160.py"

    @staticmethod
    def import_sensor_class():
        """Dynamically import and return the PositionSensor class."""
        module_name = os.path.splitext(os.path.basename(DeviceUtils.DEVICE_FILE))[0]
        spec = importlib.util.spec_from_file_location(module_name, DeviceUtils.DEVICE_FILE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return getattr(module, DeviceUtils.POSITION_SENSOR_CLASS)

    @staticmethod
    def load_sensors(sensor_class):
        """Import the test cell script and return all PositionSensor instances."""
        try:
            spec = importlib.util.spec_from_file_location("Test_Cell_1_Devices", DeviceUtils.TEST_CELL_1_SCRIPT)
            module = importlib.util.module_from_spec(spec)
            sys.modules["Test_Cell_1_Devices"] = module
            spec.loader.exec_module(module)

            sensors = [obj for obj in module.__dict__.values() if isinstance(obj, sensor_class)]
            return sensors
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load Test Cell 1 devices:\n{e}")
            return []

# -- Main Calibration Wizard Popup --
class CalibrationWizard:
    def __init__(self, sensors):
        self.sensors = sensors
        self.current_step = 0

        # Popup window
        self.win = tk.Toplevel()
        self.win.title("Position Sensor Calibration")
        self.win.geometry("400x200")

        # Instruction label
        self.label = ttk.Label(self.win, text="", font=('Arial', 12), wraplength=380)
        self.label.pack(pady=20)

        # Action button
        self.button = ttk.Button(self.win, text="", command=self.next_step)
        self.button.pack(pady=10)

        # Calibration sequence
        self.steps = [
            ("Move all pistons to fully retracted position", "Calibrate Min", self.calibrate_min),
            ("Move all pistons to fully extended position", "Calibrate Max", self.calibrate_max),
            ("✅ Sensors Calibrated!", "Close Window", self.win.destroy)
        ]

        self.show_step()

    def show_step(self):
        """Update UI for the current step."""
        if self.current_step < len(self.steps):
            msg, btn_text, _ = self.steps[self.current_step]
            self.label.config(text=msg)
            self.button.config(text=btn_text)

    def next_step(self):
        """Advance to the next step and run its action."""
        if self.current_step < len(self.steps):
            _, _, action = self.steps[self.current_step]
            action()
            self.current_step += 1
            self.show_step()

    def calibrate_min(self):
        """Call calibrate_min() on all PositionSensor instances."""
        for sensor in self.sensors:
            try:
                sensor.calibrate_min()
            except Exception as e:
                messagebox.showerror("Calibration Error", f"Failed to calibrate min:\n{e}")

    def calibrate_max(self):
        """Call calibrate_max() on all PositionSensor instances."""
        for sensor in self.sensors:
            try:
                sensor.calibrate_max()
            except Exception as e:
                messagebox.showerror("Calibration Error", f"Failed to calibrate max:\n{e}")

# -- Public Launch Function for External GUI Use --
def launch_calibration_wizard():
    """Main entry point from GUI to launch the sensor calibration popup."""
    sensor_class = DeviceUtils.import_sensor_class()
    sensors = DeviceUtils.load_sensors(sensor_class)
    if not sensors:
        messagebox.showinfo("No Sensors", "No position sensors mapped to Test Cell 1.")
        return
    CalibrationWizard(sensors)
