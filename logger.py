import csv
import threading
import time
from datetime import datetime

# Shared event message for logging one-off events from tests
_event_lock = threading.Lock()
_event_message = ""

# Per-device values reported from test scripts. Only these values are logged
# for sensor devices. The logger thread clears the value after writing it so
# sensors show ``-`` when not explicitly read.
_value_lock = threading.Lock()
_pending_values = {}


def record_event(msg: str) -> None:
    """Print ``msg`` and store it for the logger thread."""
    global _event_message
    print(msg)
    with _event_lock:
        _event_message = msg


def record_value(alias: str, value) -> None:
    """Store a sensor reading for the logger thread."""
    with _value_lock:
        _pending_values[alias] = value


class CSVLogger:
    """Background sensor logger writing rows to a CSV file."""

    def __init__(self, path, devices, interval=0.1):
        self.path = path
        self.devices = devices  # mapping alias -> object
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._fh = open(path, "w", newline="")
        self._writer = csv.writer(self._fh)
        header = ["timestamp", "time_s"] + list(devices.keys()) + ["event"]
        self._writer.writerow(header)
        self._start_time = time.time()

        # Expose the alias on each device so methods can report values
        for alias, obj in devices.items():
            try:
                setattr(obj, "_logger_alias", alias)
            except Exception:
                pass

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self._fh.close()

    def _read_value(self, obj):
        """Return the current value for always-logged devices."""
        try:
            if hasattr(obj, "active_valves"):
                return ",".join(sorted(obj.active_valves)) or "-"
            if hasattr(obj, "current_pressure"):
                return f"{obj.current_pressure}" if obj.current_pressure is not None else "-"
        except Exception:
            return "err"
        return "-"

    def _run(self):
        while not self._stop.is_set():
            ts = time.time() - self._start_time
            timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
            row = [timestamp, f"{ts:.2f}"]
            for alias, obj in self.devices.items():
                if hasattr(obj, "active_valves") or hasattr(obj, "current_pressure"):
                    row.append(self._read_value(obj))
                else:
                    with _value_lock:
                        if alias in _pending_values:
                            value = _pending_values.pop(alias)
                            row.append(str(value))
                        else:
                            row.append("-")
            with _event_lock:
                global _event_message
                msg = _event_message
                if _event_message:
                    _event_message = ""
            row.append(msg or "-")
            self._writer.writerow(row)
            self._fh.flush()
            time.sleep(self.interval)
