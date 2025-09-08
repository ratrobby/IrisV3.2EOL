try:
    from pyModbusTCP.client import ModbusClient
except Exception:  # pragma: no cover - optional dependency may be missing
    class ModbusClient:
        """Fallback stub when pyModbusTCP is unavailable."""

        def __init__(self, *args, **kwargs):
            pass

        def open(self):
            return True

        def close(self):
            pass

        def read_holding_registers(self, register, count):
            return [0] * count

        def write_single_register(self, register, value):
            return True


class IO_master:
    def __init__(self, IP_ADDR="192.168.100.1", SERVER_PORT=502, timeout=1.0):
        self._IP_ADDR = IP_ADDR
        self.SERVER_PORT = SERVER_PORT
        self.timeout = timeout
        self.client = ModbusClient(
            host=self._IP_ADDR, port=self.SERVER_PORT, timeout=self.timeout
        )

        if not self.client.open():
            raise ConnectionError(f"Unable to connect to Modbus server at {self._IP_ADDR}:{self.SERVER_PORT}")

    @property
    def IP_ADDR(self):
        return self._IP_ADDR

    @IP_ADDR.setter
    def IP_ADDR(self, value):
        self._IP_ADDR = value

    def close_client(self):
        self.client.close()

    def reopen_client(self):
        self.client.timeout = self.timeout
        if not self.client.open():
            raise ConnectionError("Failed to re-open Modbus client.")

    # Static register maps
    read_register_map = {
        1: 1002, 2: 2002, 3: 3002, 4: 4002,
        5: 5002, 6: 6002, 7: 7002, 8: 8002,
    }

    write_register_map = {
        1: 1101, 2: 2101, 3: 3101, 4: 4101,
        5: 5101, 6: 6101, 7: 7101, 8: 8101,
    }

    def id_read_register(self, port_number):
        reg = self.read_register_map.get(port_number)
        if reg is None:
            raise ValueError(f"No read register mapped to port {port_number}")
        return reg

    def id_write_register(self, port_number):
        reg = self.write_register_map.get(port_number)
        if reg is None:
            raise ValueError(f"No write register mapped to port {port_number}")
        return reg

    def read_register(self, register):
        word = self.client.read_holding_registers(register, 1)
        return word[0] if word else None

    def write_register(self, register, value):
        success = self.client.write_single_register(register, value)
        if not success:
            raise ConnectionError(f"Failed to write to register {register}")

