import os
import sys
import pytest

# Allow importing modules from the repository root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from devices.ValveBank_SY3000 import ValveBank

class FakeIOMaster:
    def __init__(self):
        self.writes = []

    def id_write_register(self, port_number):
        # Return a constant register number for simplicity
        return 1101

    def write_register(self, register, value):
        self.writes.append((register, value))


def test_valve_on_writes_correct_bitmask():
    io = FakeIOMaster()
    vb = ValveBank(io, port_number=1)
    vb.valve_on("1.A")

    # Expect a single write with the bitmask for valve 1.A
    expected = ValveBank.VALVE_BITMASKS["1.A"]
    assert io.writes[-1] == (1101, expected)


def test_valve_off_clears_bit():
    io = FakeIOMaster()
    vb = ValveBank(io, port_number=1)
    vb.valve_on("1.A")
    vb.valve_off("1.A")

    # After turning off, the bank should write zero to the register
    assert io.writes[-1] == (1101, 0)


def test_valve_pair_exclusivity():
    io = FakeIOMaster()
    vb = ValveBank(io, port_number=1)
    vb.valve_on("1.A")
    vb.valve_on("1.B")

    # Activating 1.B should automatically deactivate 1.A
    expected = ValveBank.VALVE_BITMASKS["1.B"]
    assert vb.active_valves == {"1.B"}
    assert io.writes[-1] == (1101, expected)
