import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from commands import hold, Hold

def test_hold_calls_sleep(monkeypatch):
    calls = []
    def fake_sleep(s):
        calls.append(s)
    monkeypatch.setattr(time, 'sleep', fake_sleep)
    hold(1.5)
    assert calls == [1.5]
    calls.clear()
    Hold(0.2)
    assert calls == [0.2]
