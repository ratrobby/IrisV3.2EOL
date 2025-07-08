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
_last_values = {}


def fetch_pending_value(alias: str):
    """Retrieve and clear a logged value for ``alias`` if present.

    If no new value has been recorded since the last fetch, the most
    recently logged value is returned instead. This allows the logger to
    keep reporting the latest reading even when the device isn't polled
    every logging cycle.
    """
    with _value_lock:
        if alias in _pending_values:
            val = _pending_values.pop(alias)
            _last_values[alias] = val
            return val
        return _last_values.get(alias)


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
        _last_values[alias] = value


class CSVLogger:
    """Background sensor logger writing rows to a CSV file."""

    def __init__(self, path, devices, interval=0.5, alias_names=None):
        self.path = path
        self.devices = devices  # mapping alias -> object
        self.interval = interval
        self.alias_names = alias_names or {}
        self._row_count = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._lock = threading.Lock()
        self._fh = open(path, "w", newline="")
        self._writer = csv.writer(self._fh)
        # Header includes timestamp column and one column per device alias
        header = ["timestamp"]
        for alias in devices.keys():
            header.append(self.alias_names.get(alias, alias))
        header.append("event")
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

    def insert_break(self, label=""):
        """Insert a labelled row marking a break in the log."""
        timestamp = datetime.now().isoformat(sep=" ", timespec="milliseconds")
        with self._lock:
            row = [timestamp]
            for alias in self.devices.keys():
                row.append(_last_values.get(alias, "-"))
            row.append(label or "-")
            self._writer.writerow(row)
            self._fh.flush()

    def _read_value(self, alias, obj):
        """Return the value to log for ``obj``."""
        try:
            if hasattr(obj, "log_value"):
                val = obj.log_value()
                if val not in (None, "-"):
                    return str(val)

                if hasattr(obj, "_get_force_value"):
                    force = obj._get_force_value("N")
                    val = "N/A" if force is None else f"{force:.2f}N"
                    with _value_lock:
                        _last_values[alias] = val
                    return val

                if hasattr(obj, "al2205") and hasattr(obj, "x1_index"):
                    raw = obj.al2205.read_index(obj.x1_index)
                    min_val = getattr(obj, "calibration_data", {}).get("min")
                    max_val = getattr(obj, "calibration_data", {}).get("max")
                    if (
                        raw is not None
                        and min_val is not None
                        and max_val is not None
                        and max_val != min_val
                    ):
                        span = max_val - min_val
                        pos = ((raw - min_val) / span) * obj.stroke_mm
                        result = round(max(0.0, min(pos, obj.stroke_mm)), 2)
                        val = f"{result:.2f}mm"
                    else:
                        val = "N/A"
                    with _value_lock:
                        _last_values[alias] = val
                    return val

                return "-"

            if hasattr(obj, "active_valves"):
                val = ",".join(sorted(obj.active_valves)) or "-"
                with _value_lock:
                    _last_values[alias] = val
                return val
            if hasattr(obj, "current_pressure"):
                val = f"{obj.current_pressure}" if obj.current_pressure is not None else "-"
                with _value_lock:
                    _last_values[alias] = val
                return val

            with _value_lock:
                if alias in _pending_values:
                    val = _pending_values.pop(alias)
                    _last_values[alias] = val
                    return str(val)
                return _last_values.get(alias, "-")

        except Exception:
            return "err"
        return _last_values.get(alias, "-")

    def _run(self):
        while not self._stop.is_set():
            timestamp = datetime.now().isoformat(sep=" ", timespec="milliseconds")
            row = [timestamp]

            for alias, obj in self.devices.items():
                row.append(self._read_value(alias, obj))

            with _event_lock:
                global _event_message
                msg = _event_message
                if _event_message:
                    _event_message = ""
            row.append(msg or "-")
            with self._lock:
                self._writer.writerow(row)
                self._fh.flush()
                self._row_count += 1
            time.sleep(self.interval)
