import time


class FlowPressureSensorSD9500:
    """Interface for an SD9500 combined flow and pressure sensor."""

    def __init__(
        self,
        io_master,
        port_number,
        min_cfm=0.0,
        max_cfm=100.0,
        min_psi=0.0,
        max_psi=100.0,
    ):
        """Parameters
        ----------
        io_master : IO_master
            Instance of :class:`IO_master` used for communication.
        port_number : int
            IO-Link port on the AL1342 where the sensor is connected (1-8).
        min_cfm : float, optional
            Minimum measurable flow in cubic feet per minute. Defaults to 0.0.
        max_cfm : float, optional
            Maximum measurable flow in CFM. Defaults to 100.0.
        min_psi : float, optional
            Minimum measurable pressure in PSI. Defaults to 0.0.
        max_psi : float, optional
            Maximum measurable pressure in PSI. Defaults to 100.0.
        """
        self.io = io_master
        self.port_number = port_number
        self.base_register = self.io.id_read_register(port_number)
        self.min_cfm = min_cfm
        self.max_cfm = max_cfm
        self.min_psi = min_psi
        self.max_psi = max_psi

    def _read_raw(self):
        """Return raw 16-bit values for flow and pressure."""
        regs = self.io.read_holding(self.base_register, 2)
        if regs is None or len(regs) < 2:
            return None, None
        return regs[0], regs[1]

    def _read_currents(self):
        """Return currents corresponding to flow and pressure in mA."""
        raw_flow, raw_press = self._read_raw()
        if raw_flow is None or raw_press is None:
            return None, None
        return raw_flow / 1000.0, raw_press / 1000.0

    def readVF(self):
        """Return the volumetric flow in cubic feet per minute."""
        flow_current, _ = self._read_currents()
        if flow_current is None:
            return None
        span = self.max_cfm - self.min_cfm
        return self.min_cfm + ((flow_current - 4.0) / 16.0) * span

    def readVP(self):
        """Return the pressure in PSI."""
        _, pressure_current = self._read_currents()
        if pressure_current is None:
            return None
        span = self.max_psi - self.min_psi
        return self.min_psi + ((pressure_current - 4.0) / 16.0) * span

    def monitor(self, duration=None, callback=None, stop_event=None):
        """Periodically report flow (CFM) and pressure (PSI)."""
        interval = 0.5
        start = time.time()
        try:
            while True:
                try:
                    flow = self.readVF()
                    pressure = self.readVP()
                    if callback is None:
                        if flow is None or pressure is None:
                            print("Flow = N/A, Pressure = N/A")
                        else:
                            print(f"Flow = {flow:.2f} CFM, Pressure = {pressure:.2f} PSI")
                    else:
                        callback(flow, pressure)
                except ConnectionError as exc:
                    if callback is None:
                        print(f"Error reading sensor: {exc}")
                    else:
                        callback(None, None)
                if stop_event is not None and stop_event.is_set():
                    break
                if duration is not None and (time.time() - start) >= duration:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
