import sys
import types
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from devices.ValveBank_SY3000 import ValveBank

class FakeIO:
    def id_write_register(self, port_number):
        return 1101
    def write_register(self, register, value):
        pass


def test_setup_widget_invokes_controller(monkeypatch):
    vb = ValveBank(FakeIO(), port_number=1)
    called = []
    monkeypatch.setattr(vb, "open_controller_window", lambda: called.append(True))

    created = []

    class DummyButton:
        def __init__(self, *a, command=None, **k):
            self.command = command
            created.append(self)
        def pack(self, *a, **k):
            pass
        def grid(self, *a, **k):
            pass
        def invoke(self):
            if self.command:
                self.command()

    class DummyFrame:
        def __init__(self, *a, **k):
            pass
        def pack(self, *a, **k):
            pass
        def grid(self, *a, **k):
            pass
    DummyLabel = DummyFrame

    dummy_ttk = types.SimpleNamespace(Frame=DummyFrame, Label=DummyLabel, Button=DummyButton, Checkbutton=DummyButton)
    dummy_tk = types.SimpleNamespace(IntVar=lambda value=0: 0, Toplevel=lambda: None)

    import devices.ValveBank_SY3000 as vb_mod
    monkeypatch.setattr(vb_mod, "ttk", dummy_ttk)
    monkeypatch.setattr(vb_mod, "tk", dummy_tk)

    frame = vb.setup_widget(None, name="VB", on_update=None)
    assert isinstance(frame, DummyFrame)
    assert created, "button not created"
    created[0].invoke()
    assert called
