import time

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

        def is_open(self):
            return True

        def read_holding_registers(self, register, count):
            return [0] * count

        def write_single_register(self, register, value):
            return True


class IO_master:
    def __init__(self, ip, port=502, unit_id=1, timeout=2.0):
        self._IP_ADDR = ip
        self.SERVER_PORT = port
        self.client = ModbusClient(
            host=ip,
            port=port,
            unit_id=unit_id,
            auto_open=True,
            auto_close=False,
            timeout=timeout,
        )
        self.ensure_open(attempts=4, delay=0.2)
        time.sleep(0.1)

    def ensure_open(self, attempts=3, delay=0.2):
        for i in range(attempts):
            is_open_attr = getattr(self.client, "is_open", False)
            is_open = is_open_attr() if callable(is_open_attr) else bool(is_open_attr)
            if is_open or self.client.open():
                return True
            time.sleep(delay * (i + 1))
        raise ConnectionError(
            f"Unable to connect to Modbus server at {self._IP_ADDR}:{self.SERVER_PORT}"
        )

    def read_holding(self, addr, count=1, retries=3, delay=0.15):
        """Centralized, resilient holding-register read with reopen/backoff."""
        self.ensure_open()
        for i in range(retries + 1):
            regs = self.client.read_holding_registers(addr, count)
            if regs is not None:
                return regs
            try:
                self.client.close()
            except Exception:
                pass
            time.sleep(delay * (i + 1))
            self.client.open()
        raise ConnectionError(
            f"Failed to read holding registers at {addr} (len {count})"
        )

    def prime(self, addr=0, count=1):
        """Optional: do a dummy read once to prime comms; ignore failure."""
        try:
            _ = self.read_holding(addr, count, retries=1, delay=0.1)
        except Exception:
            time.sleep(0.2)

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    # Compatibility helpers
    def close_client(self):
        self.close()

    def reopen_client(self):
        self.ensure_open()

    @property
    def IP_ADDR(self):
        return self._IP_ADDR

    @IP_ADDR.setter
    def IP_ADDR(self, value):
        self._IP_ADDR = value

    # Static register maps
    read_register_map = {
        1: 1002,
        2: 2002,
        3: 3002,
        4: 4002,
        5: 5002,
        6: 6002,
        7: 7002,
        8: 8002,
    }

    write_register_map = {
        1: 1101,
        2: 2101,
        3: 3101,
        4: 4101,
        5: 5101,
        6: 6101,
        7: 7101,
        8: 8101,
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
        regs = self.read_holding(register, 1)
        return regs[0] if regs else None

    def write_register(self, register, value):
        self.ensure_open()
        success = self.client.write_single_register(register, value)
        if not success:
            raise ConnectionError(f"Failed to write to register {register}")
        return success

