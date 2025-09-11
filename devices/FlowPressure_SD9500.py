import time, struct

class FlowPressureSensorSD9500:
    """SD9500 over IO-Link on an IFM AL1342 (reads flow in CFM, pressure in PSI)."""

    # Unit factors
    _M3H_TO_CFM = 35.3146667 / 60.0        # 1 m^3/h -> CFM
    _BAR_TO_PSI = 14.5037738               # 1 bar   -> PSI

    # Direct per-count factors (from IODD scaling)
    _FLOW_CNT_TO_CFM = 0.1 * _M3H_TO_CFM   # flow counts are 0.1 m^3/h each
    _PRES_CNT_TO_PSI = 0.01 * _BAR_TO_PSI  # pressure counts are 0.01 bar each

    @staticmethod
    def _status_reg_for_port(port_number: int) -> int:
        # X01:1001, X02:2001, ... X08:8001
        if not (1 <= port_number <= 8):
            raise ValueError("port_number must be 1..8")
        return 1001 + (port_number - 1) * 1000

    @staticmethod
    def _pdin_reg_for_port(port_number: int) -> int:
        # X01:1002, X02:2002, ... X08:8002
        if not (1 <= port_number <= 8):
            raise ValueError("port_number must be 1..8")
        return 1002 + (port_number - 1) * 1000

    def __init__(self, io_master, port_number, *, pdlen_default=16, byte_swap_override=None):
        """
        io_master must expose: read_holding(addr:int, count:int) -> list[int]
        port_number: 1..8 (AL1342 ports)
        pdlen_default: fallback PDIN length if reg 8998 can't be read
        byte_swap_override: force True/False, or None to auto from reg 8999
        """
        self.io = io_master
        self.port_number = port_number
        self.status_reg = self._status_reg_for_port(port_number)
        self.pdin_reg   = self._pdin_reg_for_port(port_number)

        # --- Read master config: process-data length (8998) and byte-swap (8999) ---
        try:
            pd_cfg = self.io.read_holding(8998, 1)
            pdlen_code = pd_cfg[0] & 0xFF
            self.pdlen_bytes = {0x00:2, 0x01:4, 0x02:8, 0x03:16, 0x04:32}[pdlen_code]
        except Exception:
            self.pdlen_bytes = int(pdlen_default)

        if byte_swap_override is None:
            try:
                swap_reg = self.io.read_holding(8999, 1)
                self.byte_swap = bool(swap_reg and (swap_reg[0] & 0xFF))
            except Exception:
                self.byte_swap = False
        else:
            self.byte_swap = bool(byte_swap_override)

    # ---- internals ----
    def _read_pqi(self) -> int:
        val = self.io.read_holding(self.status_reg, 1)
        if not val:
            raise ConnectionError("Failed to read status/PQI")
        return val[0] & 0xFF

    def _ensure_connected_iol(self):
        pqi = self._read_pqi()
        if (pqi >> 1) & 0x1:
            raise ConnectionError("Device not connected (PQI bit1).")
        if not (pqi & 0x1):
            raise ConnectionError("Port not in IO-Link mode (PQI bit0=0).")

    def _read_pdin_bytes(self) -> bytes:
        self._ensure_connected_iol()
        nregs = (self.pdlen_bytes + 1) // 2
        regs = self.io.read_holding(self.pdin_reg, nregs)
        if not regs:
            raise ConnectionError("PDIN read failed")
        out = bytearray()
        for r in regs:
            hi, lo = (r >> 8) & 0xFF, r & 0xFF
            out.extend((lo, hi) if self.byte_swap else (hi, lo))
        return bytes(out[:self.pdlen_bytes])

    # ---- public API (same names you used) ----
    def readVF(self):
        """Volumetric flow in CFM (PD bytes 4..5; Int16, 0.1 m^3/h per count)."""
        pd = self._read_pdin_bytes()
        if len(pd) < 6:
            return None
        flow_raw = struct.unpack(">h", pd[4:6])[0]
        return flow_raw * self._FLOW_CNT_TO_CFM

    def readVP(self):
        """Pressure in PSI (PD bytes 12..13; Int16, 0.01 bar per count)."""
        pd = self._read_pdin_bytes()
        if len(pd) < 14:
            return None
        pres_raw = struct.unpack(">h", pd[12:14])[0]
        return pres_raw * self._PRES_CNT_TO_PSI

    def monitor(self, duration=None, callback=None, stop_event=None, interval=0.5, debug=False):
        start = time.time()
        try:
            while True:
                try:
                    flow = self.readVF()
                    pressure = self.readVP()
                    if debug:
                        pd = self._read_pdin_bytes()
                        flow_raw = struct.unpack(">h", pd[4:6])[0] if len(pd) >= 6 else None
                        pres_raw = struct.unpack(">h", pd[12:14])[0] if len(pd) >= 14 else None
                        pqi = self._read_pqi()
                        print(f"[PQI=0x{pqi:02X} len={len(pd)} swap={self.byte_swap}] "
                              f"raw(flow={flow_raw}, pres={pres_raw})")
                    if callback:
                        callback(flow, pressure)
                    else:
                        if flow is None or pressure is None:
                            print("Flow = N/A, Pressure = N/A")
                        else:
                            print(f"Flow = {flow:.3f} CFM, Pressure = {pressure:.3f} PSI")
                except Exception as exc:
                    if callback:
                        callback(None, None)
                    else:
                        print(f"Error reading sensor: {exc}")
                if stop_event and stop_event.is_set():
                    break
                if duration and (time.time() - start) >= duration:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
