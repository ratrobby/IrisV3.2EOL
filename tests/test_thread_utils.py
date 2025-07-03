import threading
from thread_utils import start_thread


def test_start_thread_returns_thread():
    def dummy():
        return 42

    t = start_thread(dummy)
    assert isinstance(t, threading.Thread)
    t.join(timeout=1)

from devices.LoadCell_LCM300 import LoadCellLCM300

class DummyAL2205:
    def read_index(self, idx):
        return 5000


def test_device_thread_methods():
    cell = LoadCellLCM300(DummyAL2205(), 0)
    t1 = cell.read_force_thread()
    t2 = cell.monitor_force_thread(duration=0)
    assert isinstance(t1, threading.Thread)
    assert isinstance(t2, threading.Thread)
    t1.join(timeout=1)
    t2.join(timeout=1)
from devices.PositionSensor_SDAT_MHS_M160 import PositionSensorSDATMHS_M160

class DummyAL2205PS:
    def __init__(self):
        self.value = 500
    def read_index(self, idx):
        return self.value

def test_position_thread_method():
    sensor = PositionSensorSDATMHS_M160(DummyAL2205PS(), 0)
    sensor.calibration_data = {"min": 0, "max": 1000}
    t = sensor.read_position_thread()
    m = sensor.monitor_position_thread(duration=0)
    assert isinstance(t, threading.Thread)
    assert isinstance(m, threading.Thread)
    t.join(timeout=1)
    m.join(timeout=1)

