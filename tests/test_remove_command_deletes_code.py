import types
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gui.TestWizard import TestWizard

class DummyVar:
    def __init__(self, value):
        self._v = value
    def get(self):
        return self._v

class DummyRow:
    def __init__(self, seconds):
        self.command_var = DummyVar('Hold')
        self.device_var = DummyVar('General')
        self.param_vars = [('seconds', DummyVar(seconds), None)]
        self.thread_var = DummyVar(False)
        self.destroyed = False
    def destroy(self):
        self.destroyed = True

class DummyText:
    def __init__(self):
        self.contents = ''
    def delete(self, *a, **k):
        self.contents = ''
    def insert(self, index, text):
        self.contents = text


def test_remove_command_updates_loop():
    wiz = TestWizard.__new__(TestWizard)
    wiz.script_text = DummyText()

    row1 = DummyRow('1')
    row2 = DummyRow('2')
    wiz.loop_rows = [row1, row2]

    wiz.update_loop_script()
    assert 'Hold(1)' in wiz.script_text.contents
    assert 'Hold(2)' in wiz.script_text.contents

    wiz._remove_loop_row(row1)
    assert row1.destroyed
    assert 'Hold(1)' not in wiz.script_text.contents
    assert 'Hold(2)' in wiz.script_text.contents
