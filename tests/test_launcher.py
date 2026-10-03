"""Started without a console (pythonw, as the Windows launcher does), a crash must leave a trace."""

import os
import sys

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pytest.importorskip("pygame")

import seabattle.__main__ as launcher  # noqa: E402
from seabattle.__main__ import main  # noqa: E402
from seabattle.ui import app  # noqa: E402


class Broken:
    def __init__(self):
        raise RuntimeError("the boiler burst")


def test_crash_without_console_is_written_to_crash_log(tmp_path, monkeypatch):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(app, "App", Broken)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    told = []
    monkeypatch.setattr(launcher, "_tell", told.append)  # on Windows this is a message box, which would wait for a click
    assert main([]) == 1
    assert "stopped because of an error" in told[0] and str(tmp_path / "crash.log") in told[0]
    log = (tmp_path / "crash.log").read_text(encoding="utf-8")
    assert "RuntimeError: the boiler burst" in log
    assert main([]) == 1  # a second crash is added, not written over the first
    assert (tmp_path / "crash.log").read_text(encoding="utf-8").count("RuntimeError: the boiler burst") == 2


def test_crash_with_console_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(app, "App", Broken)
    with pytest.raises(RuntimeError):
        main([])
    assert not (tmp_path / "crash.log").exists()
