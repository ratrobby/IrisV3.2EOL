import types
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gui.TestWizard import TestWizard, build_instance_map

class DummyFrame:
    def __init__(self):
        self.children = []
    def winfo_children(self):
        return []
    def destroy(self):
        pass
    def pack(self, *a, **k):
        pass
    def grid(self, *a, **k):
        pass

class DummyWidget(DummyFrame):
    pass

class DummyValveBank:
    def __init__(self):
        pass
    def setup_widget(self, parent, name=None, on_update=None):
        order.append(name)
        return DummyWidget()

DummyValveBank.__name__ = "ValveBank"

class DummyRegulator:
    def setup_widget(self, parent, name=None, on_update=None):
        order.append(name)
        return DummyWidget()

DummyRegulator.__name__ = "PressureRegulatorITV1050"


def test_setup_widget_order(monkeypatch):
    cfg = {
        "al1342": {
            "X01": "ValveBank_SY3000",
            "X02": "PressureRegulator_ITV_1050",
            "X03": "PressureRegulator_ITV_1050",
            "X04": "PressureRegulator_ITV_1050",
        },
        "al2205": {},
    }
    base_map = build_instance_map(cfg)
    instance_map = base_map
    vb_alias = base_map["al1342"]["X01"]
    pr1_alias = base_map["al1342"]["X02"]
    pr2_alias = base_map["al1342"]["X03"]
    pr3_alias = base_map["al1342"]["X04"]

    device_objects = {
        vb_alias: DummyValveBank(),
        pr1_alias: DummyRegulator(),
        pr2_alias: DummyRegulator(),
        pr3_alias: DummyRegulator(),
    }

    global order
    order = []

    wiz = TestWizard.__new__(TestWizard)
    wiz.setup_frame = DummyFrame()
    wiz.instance_map = instance_map
    wiz.base_map = base_map
    wiz.device_objects = device_objects
    wiz.setup_values = {}

    dummy_ttk = types.SimpleNamespace(Button=DummyWidget)
    monkeypatch.setattr("gui.TestWizard.ttk", dummy_ttk)

    wiz.build_setup_widgets()

    assert order == [vb_alias, pr1_alias, pr2_alias, pr3_alias]
