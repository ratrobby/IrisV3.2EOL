import os
import sys

# Allow importing project modules when executed directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decorators import device_class, test_command, setup_command

@device_class
class UIButton:
    """Read a UI push button wired to an AL2205 input."""

    @classmethod
    def setup_instructions(cls):
        return []

    @classmethod
    def test_instructions(cls):
        return [
            {
                "title": "state()",
                "content": (
                    "Use: Return the interpreted state of the push button\n"
                    "Returns: 'START', 'STOP', 'HOLD', or None"
                ),
            }
        ]
    def __init__(self, al2205_instance, x1_index):
        """
        Initialize the button interface.

        Parameters:
        - al2205_instance: an instance of the AL2205 class (already tied to IO_master)
        - x1_index: which X1.x port (0–7) the button is connected to on the AL2205
        """
        self.device = al2205_instance
        self.x1_index = x1_index

        # Optional safety check if device's client is not open
       # if self.device.io_master.client is None:
         #   raise RuntimeError("Modbus client is not connected. IO_master must be properly initialized.")

    def read_button(self):
        """
        Read the digital value from the assigned AL2205 X1.x input.

        Returns:
        - Raw 16-bit unsigned value from AL2205.read_index()
        """
        return self.device.read_index(self.x1_index)

    @test_command
    def state(self):
        """
        Interpret the digital signal and return a corresponding button state.

        Returns:
        - 'START', 'STOP', 'HOLD', or None
        """
        value = self.read_button()

        if value == 257:
            return 'START'
        elif value == 1:
            return 'HOLD'
        elif value == 0:
            return 'STOP'
        else:
            return None
