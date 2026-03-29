"""Core zap helpers and bookmark I/O (no GUI / osascript)."""

from __future__ import annotations

import json

import pytest


def test_normalize_url(zap_module) -> None:
    assert zap_module.normalize_url("") == ""
    assert zap_module.normalize_url("  ") == ""
    assert zap_module.normalize_url("example.com") == "https://example.com"
    assert zap_module.normalize_url("https://a.test") == "https://a.test"


def test_load_bookmarks_empty_store(zap_module, tmp_path) -> None:
    assert zap_module.load_bookmarks() == {}
    assert (tmp_path / "zap.json").is_file()


def test_save_and_load_roundtrip_sorted_keys(zap_module, tmp_path) -> None:
    data = {"b": "https://b.test", "a": "https://a.test"}
    zap_module.save_bookmarks(data)
    raw = (tmp_path / "zap.json").read_text(encoding="utf-8")
    # Keys sorted alphabetically for stable file output
    assert raw.index('"a"') < raw.index('"b"')
    assert zap_module.load_bookmarks() == {"a": "https://a.test", "b": "https://b.test"}


def test_search_filters_and_sorts(zap_module) -> None:
    zap_module.save_bookmarks(
        {"Zebra": "https://z.example", "Alpha": "https://alpha.example"}
    )
    rows = zap_module.search("alpha")
    assert len(rows) == 1
    assert rows[0]["title"] == "Alpha"
    all_rows = zap_module.search("")
    assert [r["title"] for r in all_rows] == ["Alpha", "Zebra"]


def test_script_filter_payload_empty_query(zap_module) -> None:
    out = zap_module.script_filter_payload("")
    assert len(out["items"]) == 1
    assert out["items"][0]["valid"] is False


def test_script_filter_payload_web_command(zap_module) -> None:
    out = zap_module.script_filter_payload("web")
    assert len(out["items"]) == 1
    assert out["items"][0]["arg"] == "web"


def test_script_filter_payload_strips_leading_zap_token(zap_module) -> None:
    out = zap_module.script_filter_payload("zap web")
    assert out["items"][0]["arg"] == "web"


def test_script_filter_no_bookmark_message(zap_module) -> None:
    out = zap_module.script_filter_payload("nope-not-there")
    assert len(out["items"]) == 1
    assert "No bookmark" in out["items"][0]["title"]
