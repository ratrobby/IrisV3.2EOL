import types
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gui.TestWizard import TestWizard

class DummyCanvas:
    def __init__(self):
        self.bindings = {}
        self.scroll_calls = []
    def bind(self, event, handler, add=None):
        self.bindings[event] = handler
    def bind_all(self, event, handler):
        self.bindings[f'all_{event}'] = handler
    def unbind_all(self, event):
        self.bindings.pop(f'all_{event}', None)
    def yview_scroll(self, amount, unit):
        self.scroll_calls.append((amount, unit))


def test_mousewheel_scroll_binding():
    wiz = TestWizard.__new__(TestWizard)
    canvas = DummyCanvas()
    wiz.rows_canvas = canvas

    wiz._bind_loop_scroll()
    assert 'all_<MouseWheel>' in canvas.bindings
    assert 'all_<Button-4>' in canvas.bindings
    assert 'all_<Button-5>' in canvas.bindings

    canvas.scroll_calls.clear()
    evt = types.SimpleNamespace(delta=120, num=None)
    canvas.bindings['all_<MouseWheel>'](evt)
    assert canvas.scroll_calls[-1] == (-1, 'units')

    evt = types.SimpleNamespace(delta=0, num=4)
    canvas.bindings['all_<Button-4>'](evt)
    assert canvas.scroll_calls[-1] == (-1, 'units')

    evt = types.SimpleNamespace(delta=0, num=5)
    canvas.bindings['all_<Button-5>'](evt)
    assert canvas.scroll_calls[-1] == (1, 'units')

    wiz._unbind_loop_scroll()
    assert 'all_<MouseWheel>' not in canvas.bindings
    assert 'all_<Button-4>' not in canvas.bindings
    assert 'all_<Button-5>' not in canvas.bindings
