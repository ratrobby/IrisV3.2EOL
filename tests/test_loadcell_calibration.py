import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from devices.LoadCell_LCM300 import LoadCellLCM300

def test_calibration_steps():
    steps = LoadCellLCM300.calibration_steps()
    assert isinstance(steps, list)
    assert steps
    for step in steps:
        assert isinstance(step, dict)
        assert 'prompt' in step

