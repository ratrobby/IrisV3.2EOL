import os
import sys
import importlib
import pytest

# Allow importing modules from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def reload_testlauncher():
    import gui.TestLauncher as tl
    return importlib.reload(tl)


@pytest.mark.skipif(os.name == 'nt', reason='Non-Windows check')
def test_default_base_dir(monkeypatch):
    monkeypatch.delenv('MRLF_TEST_DIR', raising=False)
    mod = reload_testlauncher()
    expected = os.path.expanduser('~/MRLF Tests')
    assert mod.TEST_BASE_DIR == expected


@pytest.mark.skipif(os.name == 'nt', reason='Non-Windows check')
def test_env_base_dir(monkeypatch, tmp_path):
    custom = tmp_path / 'mytests'
    monkeypatch.setenv('MRLF_TEST_DIR', str(custom))
    mod = reload_testlauncher()
    assert mod.TEST_BASE_DIR == str(custom)
