import os
import sys
import types
import builtins

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import valve_bank_cli


def test_cli_exit(monkeypatch):
    calls = []

    class FakeIO:
        def __init__(self, ip, SERVER_PORT=502, timeout=1.0):
            calls.append(('init', ip, SERVER_PORT))

        def close_client(self):
            calls.append('close')

    class FakeVB:
        def __init__(self, io, port_number):
            calls.append(('vb', port_number))

        def all_off(self):
            calls.append('all_off')

        def valve_on(self, valve, duration=None):
            calls.append(('on', valve, duration))

        def valve_off(self, *valves):
            calls.append(('off', valves))

    monkeypatch.setattr(valve_bank_cli, 'IO_master', FakeIO)
    monkeypatch.setattr(valve_bank_cli, 'ValveBank', FakeVB)
    monkeypatch.setattr(sys, 'argv', ['valve_bank_cli.py'])

    inputs = iter(['exit'])
    monkeypatch.setattr(builtins, 'input', lambda _: next(inputs))

    valve_bank_cli.main()

    assert 'all_off' in calls
    assert 'close' in calls
