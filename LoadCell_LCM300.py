import time

class LoadCellLCM300:
    """Read force data from an LCM300 load cell via an AL2205 hub."""

    def __init__(self, al2205_instance, x1_index):
        """Parameters
        ----------
        al2205_instance : AL2205Hub
            Instance of :class:`AL2205Hub` used for communication.
        x1_index : int
            Channel index on the AL2205 (0–7 for X1.0–X1.7).
        """
        self.device = al2205_instance
        self.x1_index = x1_index

    def read_raw_data(self):
        """Return the raw 16-bit value from the load cell."""
        return self.device.read_index(self.x1_index)

    def read_voltage(self):
        """Convert the raw value to a voltage between 0 and 10 V."""
        raw = self.read_raw_data()
        return raw / 1000 if raw is not None else None

    def read_force(self):
        """Return the current force measurement in newtons."""
        voltage = self.read_voltage()
        if voltage is None:
            return None
        force_lbf = (5.0 - voltage) * 5
        return force_lbf * 4.44822

    def monitor_force(self, duration=None):
        """Print force readings in newtons periodically.

        Parameters
        ----------
        duration : float or None
            Total time to run in seconds. ``None`` runs until interrupted.
        """
        interval = 0.5
        start = time.time()
        try:
            while True:
                result = self.read_force()
                if result is None:
                    print("Force = N/A")
                else:
                    print(f"Force = {result:.2f}N")
                if duration is not None and (time.time() - start) >= duration:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
