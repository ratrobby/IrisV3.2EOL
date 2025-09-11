import time, struct

class FlowSensorSD6020:
    """
    SD6020 over IO-Link on an IFM AL1342 (defaults to Port X03).
    Cyclic PDIN layout (bytes):
      0..3  : Totaliser (Float32, m^3)
      4..5  : Flow (Int16, 0.01 m^3/h per count)
      6..7  : Temperature (Int16, 0.01 °C per count)
      ...   : Status/OUT bits (ignored here)
    """

    # Unit factors
    _M3H_TO_CFM = 35.3146667 / 60.0          # 1 m^3/h = 0.588577777... CFM
    _FLOW_CNT_TO_CFM = 0.01 * _M3H_TO_CFM    # 0.01 m^3/h per count

    # AL1342 single-port access helpers (X01:1001/1002, X02:2001/2002, X03:3001/3002, ...)
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

    def __init__(self, io_master, port_number: int = 3, *, pdlen_default=16, byte_swap_override=None):
        """
        io_master: object exposing read_holding(addr:int, count:int)->list[int]
        port_number: AL1342 IO-Link port (defaults to X03 -> 3)
        pdlen_default: fallback PDIN length if reg 8998 isn't readable (typical 16)
        byte_swap_override: force True/False for byte reordering; None = auto from 8999
        """
        self.io = io_master
        self.port_number = port_number
        self.status_reg = self._status_reg_for_port(port_number)
        self.pdin_reg   = self._pdin_reg_for_port(port_number)

        # Read configured PD length (8998 low byte: 00:2B, 01:4B, 02:8B, 03:16B, 04:32B)
        try:
            pd_cfg = self.io.read_holding(8998, 1)
            code = pd_cfg[0] & 0xFF
            self.pdlen_bytes = {0x00:2, 0x01:4, 0x02:8, 0x03:16, 0x04:32}[code]
        except Exception:
            self.pdlen_bytes = int(pdlen_default)

        # Read/override byte-swap (8999 low byte: 0/1)
        if byte_swap_override is None:
            try:
                swap_reg = self.io.read_holding(8999, 1)
                self.byte_swap = bool(swap_reg and (swap_reg[0] & 0xFF))
            except Exception:
                self.byte_swap = False
        else:
            self.byte_swap = bool(byte_swap_override)

    # ---------- internals ----------
    def _read_pqi(self) -> int:
        vals = self.io.read_holding(self.status_reg, 1)
        if not vals:
            raise ConnectionError("Failed to read status/PQI")
        return vals[0] & 0xFF

    def _ensure_connected_iol(self):
        pqi = self._read_pqi()
        if (pqi >> 1) & 0x1:
            raise ConnectionError(f"Device not connected on X0{self.port_number} (PQI bit1).")
        if not (pqi & 0x1):
            raise ConnectionError(f"Port X0{self.port_number} not in IO-Link mode (PQI bit0=0).")

    def _read_pdin_bytes(self) -> bytes:
        """Read PDIN bytes (sensor byte order)."""
        self._ensure_connected_iol()
        nregs = (self.pdlen_bytes + 1) // 2
        regs = self.io.read_holding(self.pdin_reg, nregs)
        if not regs:
            raise ConnectionError(f"PDIN read failed (X0{self.port_number})")
        out = bytearray()
        for r in regs:
            hi, lo = (r >> 8) & 0xFF, r & 0xFF
            out.extend((lo, hi) if self.byte_swap else (hi, lo))
        return bytes(out[:self.pdlen_bytes])

    # ---------- public API ----------
    def readPF(self):
        """Flow in CFM (from PD bytes 4..5; Int16 counts @ 0.01 m^3/h per count)."""
        pd = self._read_pdin_bytes()
        if len(pd) < 6:
            return None
        flow_raw = struct.unpack(">h", pd[4:6])[0]
        return flow_raw * self._FLOW_CNT_TO_CFM

    # Optional helpers (handy for validation / debugging)
    def read_temperature_c(self):
        pd = self._read_pdin_bytes()
        if len(pd) < 8:
            return None
        t_raw = struct.unpack(">h", pd[6:8])[0]
        return t_raw * 0.01

    def read_totaliser_m3(self):
        pd = self._read_pdin_bytes()
        if len(pd) < 4:
            return None
        return struct.unpack(">f", pd[0:4])[0]

    def read_raw(self):
        """Return raw flow/temperature counts + PQI (for debugging)."""
        pd = self._read_pdin_bytes()
        pqi = self._read_pqi()
        d = {"pqi": pqi, "len": len(pd), "byte_swap": self.byte_swap}
        d["flow_raw"] = struct.unpack(">h", pd[4:6])[0] if len(pd) >= 6 else None
        d["temp_raw"] = struct.unpack(">h", pd[6:8])[0] if len(pd) >= 8 else None
        return d

    def monitor(self, duration=None, callback=None, stop_event=None, interval=0.5, debug=False):
        """Periodically report flow (CFM)."""
        start = time.time()
        try:
            while True:
                try:
                    flow = self.readPF()
                    if debug:
                        dbg = self.read_raw()
                        print(f"[PQI=0x{dbg['pqi']:02X} len={dbg['len']} swap={dbg['byte_swap']}] "
                              f"raw(flow={dbg['flow_raw']}, temp={dbg['temp_raw']})")
                    if callback:
                        callback(flow)
                    else:
                        print("Flow = " + ("N/A" if flow is None else f"{flow:.3f} CFM"))
                except Exception as exc:
                    if callback:
                        callback(None)
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
#     io = IO_master(ip="192.168.100.1")           # must implement read_holding(addr, n)
#     sd = FlowSensorSD6020(io, port_number=3, byte_swap_override=False)  # X03
#     sd.monitor(duration=5, debug=True)
