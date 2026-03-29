"""Favicon fetch (mocked HTTP). Skipped when `workflow/favicon.py` is not in the tree."""

from __future__ import annotations

import importlib.util

import pytest

if importlib.util.find_spec("favicon") is None:
    pytest.skip("favicon module not in workflow (optional)", allow_module_level=True)

import favicon as favicon_mod


def test_fetch_favicon_from_html_link(monkeypatch: pytest.MonkeyPatch) -> None:
    page = "https://example.com/page"
    icon = "https://example.com/icon.png"
    html = b'<html><head><link rel="icon" href="/icon.png"></head></html>'
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24

    def fake_limited(url: str, limit: int):
        if url == page:
            return page, "text/html; charset=utf-8", html
        if url == icon:
            return icon, "image/png", png
        return None

    monkeypatch.setattr(favicon_mod, "fetch_limited", fake_limited)
    got = favicon_mod.fetch_favicon(page)
    assert got is not None
    data, ext = got
    assert ext == ".png"
    assert data.startswith(b"\x89PNG")


def test_fetch_favicon_returns_none_when_page_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(favicon_mod, "fetch_limited", lambda *a, **k: None)
    assert favicon_mod.fetch_favicon("https://example.com/") is None


def test_parse_sizes_max() -> None:
    assert favicon_mod._parse_sizes_max("48x48 96x96") == 96  # noqa: SLF001
