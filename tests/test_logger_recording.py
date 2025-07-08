import time
from logger import CSVLogger
from devices.LoadCell_LCM300 import LoadCellLCM300
from devices.PositionSensor_SDAT_MHS_M160 import PositionSensorSDATMHS_M160
from thread_utils import start_thread

class DummyAL2205:
    def __init__(self):
        self.value = 5000
    def read_index(self, idx):
        return self.value

class DummyAL2205PS:
    def __init__(self):
        self.value = 500
    def read_index(self, idx):
        return self.value

def test_monitor_functions_log_values(tmp_path):
    lc = LoadCellLCM300(DummyAL2205(), 0)
    ps = PositionSensorSDATMHS_M160(DummyAL2205PS(), 0)
    ps.calibration_data = {"min": 0, "max": 1000}
    log_file = tmp_path / "test.csv"
    logger = CSVLogger(str(log_file), {"lc": lc, "ps": ps}, interval=0.05)
    logger.start()
    t1 = start_thread(lc.monitor_force, "N", duration=0.2)
    t2 = start_thread(ps.monitor_position, duration=0.2)
    t1.join(timeout=1)
    t2.join(timeout=1)
    # Ensure logger captures final values
    time.sleep(0.1)
    logger.stop()
    rows = log_file.read_text().splitlines()
    assert len(rows) > 1
    headers = rows[0].split(",")
    lc_idx = headers.index("lc")
    ps_idx = headers.index("ps")
    data = [row.split(",") for row in rows[1:]]
    # Expect at least one row with numeric values
    assert any(row[lc_idx] not in {"-", "N/A"} for row in data)
    assert any(row[ps_idx] not in {"-", "N/A"} for row in data)


def test_logger_polls_without_commands(tmp_path):
    lc = LoadCellLCM300(DummyAL2205(), 0)
    ps = PositionSensorSDATMHS_M160(DummyAL2205PS(), 0)
    ps.calibration_data = {"min": 0, "max": 1000}
    log_file = tmp_path / "poll.csv"
    logger = CSVLogger(str(log_file), {"lc": lc, "ps": ps}, interval=0.05)
    logger.start()
    time.sleep(0.2)
    logger.stop()
    rows = log_file.read_text().splitlines()
    assert len(rows) > 1
    headers = rows[0].split(",")
    lc_idx = headers.index("lc")
    ps_idx = headers.index("ps")
    data = [row.split(",") for row in rows[1:]]
    assert any(row[lc_idx] not in {"-", "N/A"} for row in data)
    assert any(row[ps_idx] not in {"-", "N/A"} for row in data)
