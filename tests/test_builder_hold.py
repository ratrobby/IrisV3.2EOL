import types
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gui.TestWizard import TestWizard

class DummyVar:
    def __init__(self, value=""):
        self._v = value
    def get(self):
        return self._v
    def set(self, value):
        self._v = value


def make_wizard():
    wiz = TestWizard.__new__(TestWizard)
    wiz.loop_sections = []
    wiz.step_mode_var = DummyVar(False)

    def add_section(add_row=True):
        sec = types.SimpleNamespace(name_var=DummyVar(""), loop_rows=[])
        wiz.loop_sections.append(sec)
        if add_row:
            add_loop_row(sec)
        return sec

    def add_loop_row(section):
        row = types.SimpleNamespace(
            device_var=DummyVar(""),
            command_var=DummyVar(""),
            param_vars=[],
            thread_var=DummyVar(False),
            hold_var=DummyVar("0"),
        )
        section.loop_rows.append(row)
        return row

    wiz.add_section = add_section
    wiz.add_loop_row = add_loop_row
    wiz._update_row_commands = lambda row: None
    wiz._build_param_fields = lambda row: None
    wiz.update_loop_script = lambda: None

    return wiz


def test_serialize_loop_builder_includes_hold():
    wiz = make_wizard()
    sec = types.SimpleNamespace(name_var=DummyVar("sec"), loop_rows=[])
    row = types.SimpleNamespace(
        device_var=DummyVar("General"),
        command_var=DummyVar("Hold"),
        param_vars=[("seconds", DummyVar("1"), None)],
        thread_var=DummyVar(False),
        hold_var=DummyVar("2"),
    )
    sec.loop_rows.append(row)
    wiz.loop_sections = [sec]

    builder = wiz._serialize_loop_builder()
    assert builder["sections"][0]["steps"][0]["hold"] == "2"


def test_load_loop_builder_sets_hold_var():
    wiz = make_wizard()
    builder = {
        "step_mode": False,
        "sections": [
            {
                "name": "sec",
                "steps": [
                    {
                        "device": "General",
                        "command": "Hold",
                        "params": {"seconds": "1"},
                        "thread": False,
                        "hold": "3",
                    }
                ],
            }
        ],
    }
    wiz._load_loop_builder(builder)
    assert wiz.loop_sections[0].loop_rows[0].hold_var.get() == "3"
