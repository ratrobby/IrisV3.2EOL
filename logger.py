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


def fetch_pending_value(alias: str):
    """Retrieve and clear a logged value for ``alias`` if present."""
    with _value_lock:
        return _pending_values.pop(alias, None)


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

    def __init__(self, path, devices, interval=0.5):
        self.path = path
        self.devices = devices  # mapping alias -> object
        self.interval = interval
        self._row_count = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._fh = open(path, "w", newline="")
        self._writer = csv.writer(self._fh)
        # Header includes time column and one column per device alias
        header = ["time"] + list(devices.keys()) + ["event"]
        self._writer.writerow(header)

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

    def _read_value(self, alias, obj):
        """Return the value to log for ``obj``."""
        try:
            if hasattr(obj, "log_value"):
                val = obj.log_value()
                return "-" if val is None else str(val)

            if hasattr(obj, "active_valves"):
                return ",".join(sorted(obj.active_valves)) or "-"
            if hasattr(obj, "current_pressure"):
                return f"{obj.current_pressure}" if obj.current_pressure is not None else "-"

            with _value_lock:
                if alias in _pending_values:
                    return str(_pending_values.pop(alias))

        except Exception:
            return "err"
        return "-"

    def _run(self):
        while not self._stop.is_set():
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            row = [timestamp]

            for alias, obj in self.devices.items():
                row.append(self._read_value(alias, obj))

            with _event_lock:
                global _event_message
                msg = _event_message
                if _event_message:
                    _event_message = ""
            row.append(msg or "-")
            self._writer.writerow(row)
            self._fh.flush()
            self._row_count += 1
            time.sleep(self.interval)
