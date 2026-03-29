"""Pytest fixtures: isolate Zap data dir per test via DATA_PATH + reload zap module."""

from __future__ import annotations

import importlib
from typing import Generator

import pytest


@pytest.fixture
def zap_module(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Generator:
    """Fresh `zap` module bound to tmp_path (zap.json under tmp_path)."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    import zap

    importlib.reload(zap)
    yield zap
    importlib.reload(zap)
