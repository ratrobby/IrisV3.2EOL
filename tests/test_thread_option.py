import types
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gui.TestWizard import TestWizard

class DummyVar:
    def __init__(self, value=None):
        self._v = value
    def get(self):
        return self._v

class DummyText:
    def __init__(self):
        self.contents = None
    def delete(self, *a, **k):
        pass
    def insert(self, index, text):
        self.contents = text


def test_thread_checkbox_generates_start_thread():
    wiz = TestWizard.__new__(TestWizard)
    wiz.script_text = DummyText()
    row = types.SimpleNamespace(
        command_var=DummyVar('Hold'),
        device_var=DummyVar('General'),
        param_vars=[('seconds', DummyVar('1'), None)],
        thread_var=DummyVar(True),
    )
    class DummySection:
        def __init__(self, rows):
            self.name_var = DummyVar('sec')
            self.loop_rows = rows
    section = DummySection([row])
    row.section = section
    wiz.loop_sections = [section]
    wiz.update_loop_script()
    assert 'start_thread' in wiz.script_text.contents

