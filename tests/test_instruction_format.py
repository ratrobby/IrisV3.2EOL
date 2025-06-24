import os
import sys
import types
import importlib
import inspect

# Allow importing modules from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Provide a minimal scipy.interpolate interp1d stub if scipy isn't available
if 'scipy' not in sys.modules:
    scipy_mod = types.ModuleType('scipy')
    interpolate_mod = types.ModuleType('scipy.interpolate')
    def interp1d(*args, **kwargs):
        raise NotImplementedError
    interpolate_mod.interp1d = interp1d
    scipy_mod.interpolate = interpolate_mod
    sys.modules['scipy'] = scipy_mod
    sys.modules['scipy.interpolate'] = interpolate_mod

DEVICES_DIR = os.path.join(os.path.dirname(__file__), '..', 'devices')


def get_device_classes(module):
    """Return all classes decorated as device_class in a module."""
    return [obj for name, obj in inspect.getmembers(module, inspect.isclass)
            if getattr(obj, '_is_device_class', False)]


def validate_instructions(cls, method_name):
    method = getattr(cls, method_name, None)
    if method is None:
        return
    result = method()
    assert isinstance(result, list), f"{cls.__name__}.{method_name} should return a list"
    for entry in result:
        assert isinstance(entry, dict), f"{cls.__name__}.{method_name} entries must be dicts"
        assert 'title' in entry and 'content' in entry, (
            f"{cls.__name__}.{method_name} entries must have 'title' and 'content'")


def test_instruction_format():
    for fname in os.listdir(DEVICES_DIR):
        if not fname.endswith('.py') or fname == '__init__.py':
            continue
        mod_name = f"devices.{fname[:-3]}"
        mod = importlib.import_module(mod_name)
        for cls in get_device_classes(mod):
            validate_instructions(cls, 'setup_instructions')
            validate_instructions(cls, 'test_instructions')


