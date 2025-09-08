class AL2205Hub:
    """Interface to an AL2205 IO-Link hub connected to an AL1342."""

    def __init__(self, io_master, port_number):
        """Initialize the interface.

        Parameters
        ----------
        io_master : IO_master
            Modbus communication handler for the AL1342.
        port_number : int
            IO-Link port on the AL1342 where the AL2205 is connected (1-8).
        """
        self.io = io_master
        self.port_number = port_number

        if port_number not in self.io.read_register_map:
            raise ValueError(f"Invalid port number: {port_number}")

        self.base_register = self.io.id_read_register(port_number)

    def read_index(self, x1_index, count=1):
        """Return the raw 16-bit value from the specified X1 port.

        Parameters
        ----------
        x1_index : int
            Channel index on the AL2205 (0–7 for X1.0–X1.7).
        count : int, optional
            Number of consecutive registers to read starting at the index.
        """
        word_map = {
            0: 1,
            1: 4,
            2: 5,
            3: 6,
            4: 7,
            5: 8,
            6: 9,
            7: 10,
        }
        word_offset = word_map.get(x1_index)
        if word_offset is None:
            raise ValueError("Invalid X1 index. Must be between 0 and 7.")

        register = self.base_register + word_offset
        regs = self.io.read_holding(register, count, retries=3, delay=0.15)
        return regs[0] if count == 1 else regs
