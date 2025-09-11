import types
import sys
import importlib

class DummyIO:
    def __init__(self, ip):
        pass
    def prime(self, addr=1008, count=1):
        pass
    def close_client(self):
        pass

class DummyHub:
    def __init__(self, io, port_number):
        pass

class DummyLoadCell:
    def __init__(self, hub, x1_index):
        self.index = x1_index
    def read_force(self):
        return 10.0 * (self.index + 1)

class DummyPressure:
    def __init__(self, hub, x1_index):
        pass

class DummyFlowPressure:
    def __init__(self, io, port_number):
        pass

class DummyFlow:
    def __init__(self, io, port_number):
        pass

sys.modules['IO_master'] = types.SimpleNamespace(IO_master=DummyIO)
sys.modules['AL2205_Hub'] = types.SimpleNamespace(AL2205Hub=DummyHub)
sys.modules['LoadCell_LCM300'] = types.SimpleNamespace(LoadCellLCM300=DummyLoadCell)
sys.modules['PressureSensor_PQ3834'] = types.SimpleNamespace(PressureSensorPQ3834=DummyPressure)
sys.modules['FlowPressure_SD9500'] = types.SimpleNamespace(FlowPressureSensorSD9500=DummyFlowPressure)
sys.modules['FlowSensor_SD6020'] = types.SimpleNamespace(FlowSensorSD6020=DummyFlow)

cmds = importlib.import_module('Iris_EOL_Sensor_Commands')

def test_read_multiple_cells(capsys):
    cmds.readLC(1,2,3)
    out = capsys.readouterr().out.strip().splitlines()
    assert out == [
        'LC1: 10.00 N',
        'LC2: 20.00 N',
        'LC3: 30.00 N',
    ]
