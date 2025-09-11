import time, struct


class FlowPressureSensorSD9500:
    """
    SD9500 over IO-Link on an IFM AL1342.
    - Flow  (bytes 4..5):   Int16, 0.1 m^3/h per count  -> CFM
    - Temp  (bytes 8..9):   Int16, 0.01 °C per count    -> °C   (available via read_temperature)
    - Press (bytes 12..13): Int16, 0.01 bar per count   -> PSI
    """

    # Unit factors
    _M3H_TO_CFM = 35.3146667 / 60.0          # 1 m^3/h = 0.588577777... CFM
    _BAR_TO_PSI = 14.5037738                 # 1 bar   = 14.5037738 PSI

    # Derived direct-per-count factors (from IO-Link scaling above)
    _FLOW_CNT_TO_CFM = 0.1 * _M3H_TO_CFM     # 0.1 m^3/h per count
    _PRES_CNT_TO_PSI = 0.01 * _BAR_TO_PSI    # 0.01 bar  per count

    # AL1342 per-port register base (single-port access area)
    # X01: status=1001, pdin=1002; X02: 2001/2002; ... X08: 8001/8002
    @staticmethod
    def _status_reg_for_port(port_number: int) -> int:
        if not (1 <= port_number <= 8):
            raise ValueError("port_number must be 1..8")
        return 1001 + (port_number - 1) * 1000

    @staticmethod
    def _pdin_reg_for_port(port_number: int) -> int:
        if not (1 <= port_number <= 8):
            raise ValueError("port_number must be 1..8")
        return 1002 + (port_number - 1) * 1000

    def __init__(self, io_master, port_number, *, pdlen_default=16, byte_swap_override=None):
        """
        io_master: object exposing read_holding(addr:int, count:int)->list[int]
        port_number: 1..8 (AL1342 IO-Link port)
        pdlen_default: used if 8998 can't be read; typical is 16 bytes
        byte_swap_override: set True/False to force byte-swap handling; None = auto from 8999
        """
        self.io = io_master
        self.port_number = port_number
        self.status_reg = self._status_reg_for_port(port_number)
        self.pdin_reg   = self._pdin_reg_for_port(port_number)

        # ---- Read master config: process-data length & byte-swap ----
        # 8998 low byte = PD length code   (00:2B, 01:4B, 02:8B, 03:16B, 04:32B)
        # 8999 low byte = byte-swap flag   (0: off, 1: on)
        try:
            pd_cfg = self.io.read_holding(8998, 1)
            if not pd_cfg:
                raise RuntimeError
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

    # ---------- low-level helpers ----------
    def _read_pqi(self) -> int:
        """Return PQI (low byte of status reg)."""
        val = self.io.read_holding(self.status_reg, 1)
        if not val:
            raise ConnectionError("Failed to read status/PQI")
        return val[0] & 0xFF

    def _ensure_connected_iol(self):
        pqi = self._read_pqi()
        dev_not_conn = (pqi >> 1) & 0x1
        iol_mode     =  pqi       & 0x1
        if dev_not_conn:
            raise ConnectionError("Device not connected on this port (PQI bit1).")
        if not iol_mode:
            raise ConnectionError("Port not in IO-Link mode (PQI bit0=0).")

    def _read_pdin_bytes(self) -> bytes:
        """Read PDIN bytes for this port (sensor byte order)."""
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

    # ---------- public reads ----------
    def readVF(self):
        """Volumetric flow in CFM."""
        pd = self._read_pdin_bytes()
        if len(pd) < 6:
            return None
        flow_raw = struct.unpack(">h", pd[4:6])[0]     # counts, 0.1 m^3/h per count
        return flow_raw * self._FLOW_CNT_TO_CFM

    def readVP(self):
        """Pressure in PSI."""
        pd = self._read_pdin_bytes()
        if len(pd) < 14:
            return None
        pres_raw = struct.unpack(">h", pd[12:14])[0]   # counts, 0.01 bar per count
        return pres_raw * self._PRES_CNT_TO_PSI

    # Optional extras (handy for debugging/validation)
    def read_temperature_c(self):
        """Temperature in °C (optional)."""
        pd = self._read_pdin_bytes()
        if len(pd) < 10:
            return None
        temp_raw = struct.unpack(">h", pd[8:10])[0]
        return temp_raw * 0.01

    def read_totaliser_m3(self):
        """Totalised volume in m^3 (optional)."""
        pd = self._read_pdin_bytes()
        if len(pd) < 4:
            return None
        return struct.unpack(">f", pd[0:4])[0]

    def read_raw_fields(self):
        """Return a dict with raw counts + PQI (for troubleshooting)."""
        pd = self._read_pdin_bytes()
        pqi = self._read_pqi()
        d = {"pqi": pqi, "len": len(pd), "byte_swap": self.byte_swap}
        d["flow_raw"] = struct.unpack(">h", pd[4:6])[0] if len(pd) >= 6 else None
        d["temp_raw"] = struct.unpack(">h", pd[8:10])[0] if len(pd) >= 10 else None
        d["pres_raw"] = struct.unpack(">h", pd[12:14])[0] if len(pd) >= 14 else None
        return d

    def monitor(self, duration=None, callback=None, stop_event=None, interval=0.5, debug=False):
        """
        Periodically report flow (CFM) and pressure (PSI).
        If debug=True, also prints raw counts and PQI.
        """
        start = time.time()
        try:
            while True:
                try:
                    flow = self.readVF()
                    pressure = self.readVP()
                    if debug:
                        dbg = self.read_raw_fields()
                        print(f"[PQI={dbg['pqi']:02X} len={dbg['len']} swap={dbg['byte_swap']}] "
                              f"raw(flow={dbg['flow_raw']} cnt, pres={dbg['pres_raw']} cnt)")
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

# ---- Example usage (uncomment and adapt) ----
# if __name__ == "__main__":
#     from your_io_master import IO_master
#     io = IO_master(ip="192.168.100.1")         # must implement read_holding(addr, n)
#     sd = FlowPressureSensorSD9500(io, port_number=2)  # X02
#     sd.monitor(duration=5, debug=True)

