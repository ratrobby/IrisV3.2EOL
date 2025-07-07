import csv
import threading
import time
from datetime import datetime

# Shared event message for logging one-off events from tests
_event_lock = threading.Lock()
_event_message = ""


def record_event(msg: str) -> None:
    """Print ``msg`` and store it for the logger thread."""
    global _event_message
    print(msg)
    with _event_lock:
        _event_message = msg


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
        self._row_count = 0

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self._fh.close()

    def _read_value(self, obj):
        try:
            if hasattr(obj, "_get_force_value"):
                val = obj._get_force_value("N")
                return f"{val:.3f}" if val is not None else "N/A"
            if hasattr(obj, "read_position"):
                val = obj.read_position()
                return f"{val:.2f}"
            if hasattr(obj, "active_valves"):
                return ",".join(sorted(obj.active_valves)) or "-"
            if hasattr(obj, "current_pressure"):
                if self._row_count == 0:
                    return f"{obj.current_pressure}"
                return "-"
        except Exception:
            return "err"
        return "-"

    def _run(self):
        while not self._stop.is_set():
            ts = time.time() - self._start_time
            timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
            row = [timestamp, f"{ts:.2f}"]
            for obj in self.devices.values():
                row.append(self._read_value(obj))
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
