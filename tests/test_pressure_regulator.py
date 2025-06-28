import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from devices.PressureRegulator_ITV_1050 import PressureRegulatorITV1050


class FakeIOMaster:
    def __init__(self):
        self.writes = []
        self.read_val = 0

    def id_write_register(self, port_number):
        return 1102

    def id_read_register(self, port_number):
        return 1002

    def write_register(self, register, value):
        self.writes.append((register, value))
        self.read_val = value

    def read_register(self, register):
        return self.read_val


def test_instantiation_builds_curve():
    io = FakeIOMaster()
    pr = PressureRegulatorITV1050(io, port_number=1)
    assert callable(pr.command_correction)


def test_set_pressure_simple():
    io = FakeIOMaster()
    pr = PressureRegulatorITV1050(io, port_number=1)
    result = pr.set_pressure(50)
    expected_raw = int(pr.command_correction(50))
    assert io.writes[-1] == (1102, expected_raw)
    assert result is True
