import os
import sys

# Allow importing project modules when executed directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decorators import device_class
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
    - read_force(unit="lbf"): Return force in pounds-force or newtons.

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
                    "Use: Returns force of load cell in pounds-force or newtons\n"
                    "Inputs:\n"
                    "  - unit: Defines the unit of force the reading will be in\n"
                    "          - lbf: pounds-force\n"
                    "          - N: Newtons\n"
                    "Example:\n"
                    "  - read_force(N) - Reads force in newtons\n"
                    "  - read_force(lbf) - Reads force in pounds-force"
                ),
            }
        ]

    @classmethod
    def setup_instructions(cls):
        return []

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

    def read_force(self, unit="lbf"):
        """
        Convert voltage to force.

        Parameters:
        - unit: "lbf" for pounds-force or "n" for newtons

        Returns:
        - Force in requested unit (float)
        """
        voltage = self.read_voltage()
        if voltage is None:
            return None

        # Example calibration: 5 V = 0 lbf, 0 V = 50 lbf (10 lbf/V)
        force_lbf = (5.0 - voltage) * 10.0

        unit = unit.lower()
        if unit == "lbf":
            return force_lbf
        elif unit == "n":
            return force_lbf * 4.44822
        else:
            raise ValueError("Invalid unit. Use 'lbf' or 'n'.")
