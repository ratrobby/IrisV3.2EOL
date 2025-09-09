import time

class PressureSensorPQ3834:
    """Interface for an IFM PQ3834 pressure sensor."""

    def __init__(self, al2205_instance, x1_index, min_bar=-1.0, max_bar=10.5):
        """Parameters
        ----------
        al2205_instance : AL2205Hub
            Instance of :class:`AL2205Hub` used for communication.
        x1_index : int
            Channel index on the AL2205 (0–7 for X1.0–X1.7).
        min_bar : float, optional
            Minimum measurable pressure in bar.  Defaults to -1.0.
        max_bar : float, optional
            Maximum measurable pressure in bar.  Defaults to 10.5.
        """
        self.device = al2205_instance
        self.x1_index = x1_index
        self.min_bar = min_bar
        self.max_bar = max_bar

    def read_raw_data(self):
        """Return the raw 16-bit value from the sensor."""
        val = self.device.read_index(self.x1_index)
        if isinstance(val, list):
            return val[0]
        return val

    def read_voltage(self):
        """Convert the raw value to a voltage between 0 and 10 V."""
        raw = self.read_raw_data()
        return raw / 1000 if raw is not None else None

    def read_pressure(self):
        """Return the current pressure in PSI."""
        voltage = self.read_voltage()
        if voltage is None:
            return None
        span = self.max_bar - self.min_bar
        bar = self.min_bar + (voltage / 10.0) * span
        return bar * 14.5037738

    def monitor_pressure(self, duration=None, callback=None, stop_event=None):
        """Periodically report pressure readings in PSI."""
        interval = 0.5
        start = time.time()
        try:
            while True:
                try:
                    result = self.read_pressure()
                    if callback is None:
                        if result is None:
                            print("Pressure = N/A")
                        else:
                            print(f"Pressure = {result:.2f} PSI")
                    else:
                        callback(result)
                except ConnectionError as exc:
                    if callback is None:
                        print(f"Error reading pressure: {exc}")
                    else:
                        callback(None)
                if stop_event is not None and stop_event.is_set():
                    break
                if duration is not None and (time.time() - start) >= duration:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
