"""Tests for action.py CLI entrypoint wrapper."""

from __future__ import annotations

import runpy
from types import SimpleNamespace

import action


def test_main_requires_action_arg(monkeypatch, capsys) -> None:
    monkeypatch.setattr(action.sys, "argv", ["action.py"])
    assert action.main() == 1
    assert "Missing action arg" in capsys.readouterr().out


def test_main_opens_http_url(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(cmd: list[str], check: bool = False):
        assert check is False
        calls.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(action.subprocess, "run", _run)
    monkeypatch.setattr(action.sys, "argv", ["action.py", "https://example.com/path"])

    assert action.main() == 0
    assert calls == [["open", "https://example.com/path"]]


def test_main_dispatches_non_url_to_zap_action(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(cmd: list[str], check: bool = False):
        assert check is False
        calls.append(cmd)
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(action.subprocess, "run", _run)
    monkeypatch.setattr(action.sys, "argv", ["action.py", "del::My", "Bookmark"])

    assert action.main() == 7
    assert calls
    assert calls[0][0] == "python3"
    assert calls[0][1].endswith("/zap.py")
    assert calls[0][2:] == ["--action", "del::My Bookmark"]


def test_action_dunder_main_executes_main(monkeypatch, capsys) -> None:
    monkeypatch.setattr(action.sys, "argv", ["action.py"])
    try:
        runpy.run_path(action.__file__, run_name="__main__")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1
    assert "Missing action arg" in capsys.readouterr().out
