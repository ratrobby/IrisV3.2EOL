import os
import sys

# Allow importing project modules when executed directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decorators import test_command, setup_command

class AL2205:


    def __init__(self, io_master, port_number):
        """
        Initialize the AL2205 module interface.

        Parameters:
        - io_master: an instance of IO_master that handles Modbus communication
        - port_number: the IO-Link port number (1–8) where this AL2205 is connected on the AL1342
        """
        self.io_master = io_master
        self.port_number = port_number

        # Get base register directly from IO_master's mapping
        if port_number not in self.io_master.read_register_map:
            raise ValueError(f"Invalid port number: {port_number}")

        self.base_register = self.io_master.id_read_register(port_number)


    @test_command
    def read_index(self, X1_index):
        """
        Read the raw 16-bit unsigned analog signal value from a specific X1.x port.

        Parameters:
        - x1_index: index of the port on the AL2205 (0–7 for X1.0 to X1.7)

        Returns:
        - A raw unsigned integer between 0 and 65535
        """
        word_map = {
            0: 1,  # X1.0 = Word 6
            1: 4,  # X1.1 = Word 8
            2: 5,
            3: 6,
            4: 7,
            5: 8,
            6: 9,
            7: 10
        }

        word_offset = word_map.get(X1_index)
        if word_offset is None:
            raise ValueError("Invalid X1 index for analog read. Must be between 0 and 7.")

        register = self.base_register + word_offset
        result = self.io_master.read_register(register)

        if result is not None:
            return result  # Already a raw 16-bit integer
        else:
            raise ConnectionError(f"Failed to read analog input register at {register}")

