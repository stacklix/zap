"""Additional coverage tests for favicon.py branches and fallbacks."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

import favicon as favicon_mod


def test_request_and_ssl_context() -> None:
    req = favicon_mod._request("https://example.com")  # noqa: SLF001
    assert req.full_url == "https://example.com"
    assert req.get_method() == "GET"
    assert req.headers.get("User-agent")
    assert favicon_mod._ssl_context() is not None  # noqa: SLF001


def test_content_type_variants() -> None:
    class _Headers1:
        def get_content_type(self):
            return "image/png"

    class _Headers2:
        def get_content_type(self):
            raise RuntimeError("boom")

        def get(self, name: str, default: str = ""):
            assert name == "Content-Type"
            return "text/html; charset=utf-8"

    assert favicon_mod._content_type(None) == ""  # noqa: SLF001
    assert favicon_mod._content_type(_Headers1()) == "image/png"  # noqa: SLF001
    assert favicon_mod._content_type(_Headers2()) == "text/html"  # noqa: SLF001
    assert favicon_mod._content_type(object()) == ""  # noqa: SLF001


def test_fetch_limited_success_and_limit_and_errors(monkeypatch) -> None:
    class _Resp:
        def __init__(self, body: bytes) -> None:
            self.headers = {"Content-Type": "image/png"}
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self) -> str:
            return "https://final.example/x.png"

        def read(self, _n: int) -> bytes:
            return self._body

    monkeypatch.setattr(favicon_mod, "_content_type", lambda _h: "image/png")
    monkeypatch.setattr(favicon_mod, "urlopen", lambda *a, **k: _Resp(b"abc"))
    out = favicon_mod.fetch_limited("https://x", 10)
    assert out == ("https://final.example/x.png", "image/png", b"abc")

    monkeypatch.setattr(favicon_mod, "urlopen", lambda *a, **k: _Resp(b"0123456789X"))
    assert favicon_mod.fetch_limited("https://x", 10) is None

    def _raise(exc):
        def _inner(*_a, **_k):
            raise exc

        return _inner

    assert favicon_mod.fetch_limited("https://x", 10) is None
    monkeypatch.setattr(favicon_mod, "urlopen", _raise(URLError("u")))
    assert favicon_mod.fetch_limited("https://x", 10) is None
    monkeypatch.setattr(favicon_mod, "urlopen", _raise(HTTPError("https://x", 500, "e", {}, None)))
    assert favicon_mod.fetch_limited("https://x", 10) is None
    monkeypatch.setattr(favicon_mod, "urlopen", _raise(OSError("e")))
    assert favicon_mod.fetch_limited("https://x", 10) is None
    monkeypatch.setattr(favicon_mod, "urlopen", _raise(ValueError("e")))
    assert favicon_mod.fetch_limited("https://x", 10) is None


def test_ext_from_type_and_looks_like_image() -> None:
    assert favicon_mod._ext_from_type("image/svg+xml", "https://x/a") == ".svg"  # noqa: SLF001
    assert favicon_mod._ext_from_type("image/png", "https://x/a") == ".png"  # noqa: SLF001
    assert favicon_mod._ext_from_type("image/jpeg", "https://x/a") == ".jpg"  # noqa: SLF001
    assert favicon_mod._ext_from_type("image/webp", "https://x/a") == ".webp"  # noqa: SLF001
    assert favicon_mod._ext_from_type("image/x-icon", "https://x/a") == ".ico"  # noqa: SLF001
    assert favicon_mod._ext_from_type("", "https://x/a.jpeg") == ".jpg"  # noqa: SLF001
    assert favicon_mod._ext_from_type("", "https://x/a.png") == ".png"  # noqa: SLF001
    assert favicon_mod._ext_from_type("", "https://x/a.ico") == ".ico"  # noqa: SLF001
    assert favicon_mod._ext_from_type("", "https://x/a.svg") == ".svg"  # noqa: SLF001
    assert favicon_mod._ext_from_type("", "https://x/a.webp") == ".webp"  # noqa: SLF001
    assert favicon_mod._ext_from_type("", "https://x/a.unknown") == ".ico"  # noqa: SLF001

    assert favicon_mod._looks_like_image(b"", ".png") is False  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"\x89PNG\r\n\x1a\nxxxx", ".png") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"GIF89a", ".gif") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"\xff\xd8xxxx", ".jpg") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"RIFFxxxxWEBPmore", ".webp") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"\x00\x00\x01\x00icon", ".ico") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"\x00\x00\x02\x00icon", ".ico") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"<?xml version='1.0'?><svg/>", ".svg") is True  # noqa: SLF001
    assert favicon_mod._looks_like_image(b"not image", ".png") is False  # noqa: SLF001


def test_rel_tokens_candidate_score_and_sorted_hrefs() -> None:
    assert favicon_mod._rel_tokens("a  b") == ["a", "b"]  # noqa: SLF001
    assert favicon_mod._candidate_score("stylesheet", "16x16") is None  # noqa: SLF001
    assert favicon_mod._candidate_score("mask-icon", "16x16") is None  # noqa: SLF001
    assert favicon_mod._candidate_score("icon mask-icon", "16x16") is None  # noqa: SLF001
    assert favicon_mod._candidate_score("icon", "32x32") == (400, 32)  # noqa: SLF001
    assert favicon_mod._candidate_score("apple-touch-icon", "180x180") == (300, 180)  # noqa: SLF001
    assert favicon_mod._candidate_score("shortcut icon", "16x16") == (400, 16)  # noqa: SLF001
    assert favicon_mod._candidate_score("shortcut", "16x16") is None  # noqa: SLF001

    links = [
        ("icon", "/a.png", "32x32"),
        ("apple-touch-icon", "/b.png", "180x180"),
        ("icon", "/a.png", "32x32"),  # duplicate URL should be deduped
        ("shortcut icon", "/c.ico", "16x16"),
        ("mask-icon", "/d.svg", "any"),
        ("stylesheet", "/e.css", "any"),  # skipped by candidate_score(None)
    ]
    hrefs = favicon_mod._sorted_hrefs(links, "https://example.com/path/page")  # noqa: SLF001
    assert hrefs == [
        "https://example.com/a.png",
        "https://example.com/c.ico",
        "https://example.com/b.png",
    ]

    parser = favicon_mod._LinkParser()  # noqa: SLF001
    parser.handle_starttag("link", [("rel", "icon"), ("href", ""), ("sizes", "16x16")])
    assert parser.links == []


def test_fetch_favicon_image_html_and_fallback_paths(monkeypatch) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    ico = b"\x00\x00\x01\x00" + b"\x00" * 8

    # Case 1: page itself is image.
    monkeypatch.setattr(favicon_mod, "fetch_limited", lambda *_a, **_k: ("https://x/i.png", "image/png", png))
    got = favicon_mod.fetch_favicon("https://x/page")
    assert got == (png, ".png")

    # Case 2: html with links; first link invalid, second valid.
    html = b"""
    <html><head>
      <link rel='icon' href='/bad.ico' sizes='16x16'>
      <link rel='icon' href='/good.png' sizes='64x64'>
    </head></html>
    """

    def _fetch(url: str, _limit: int):
        if url == "https://site/page":
            return ("https://site/page", "text/html", html)
        if url == "https://site/bad.ico":
            return ("https://site/bad.ico", "image/x-icon", b"nope")
        if url == "https://site/good.png":
            return ("https://site/good.png", "image/png", png)
        if url == "https://site/favicon.ico":
            return ("https://site/favicon.ico", "image/x-icon", ico)
        return None

    monkeypatch.setattr(favicon_mod, "fetch_limited", _fetch)
    got = favicon_mod.fetch_favicon("https://site/page")
    assert got == (png, ".png")

    # Case 3: html parse error then fallback favicon.ico.
    class _BrokenParser:
        def __init__(self):
            self.links = []

        def feed(self, _text):
            raise RuntimeError("bad html")

        def close(self):
            return None

    monkeypatch.setattr(favicon_mod, "_LinkParser", _BrokenParser)
    got = favicon_mod.fetch_favicon("https://site/page")
    assert got == (ico, ".ico")

    # Case 4: page cannot be fetched.
    monkeypatch.setattr(favicon_mod, "fetch_limited", lambda *_a, **_k: None)
    assert favicon_mod.fetch_favicon("https://none/page") is None


def test_fetch_favicon_decode_and_fallback_failure(monkeypatch) -> None:
    ico = b"\x00\x00\x01\x00" + b"\x00" * 8

    class _BadBytes(bytes):
        def decode(self, *_args, **_kwargs):
            raise RuntimeError("decode failed")

    # Cover decode exception branch and fallback success.
    def _fetch_decode(url: str, _limit: int):
        if url == "https://d/page":
            return ("https://d/page", "text/html", _BadBytes(b"\xff\xfe\x00\x00"))
        if url == "https://d/favicon.ico":
            return ("https://d/favicon.ico", "image/x-icon", ico)
        return None

    monkeypatch.setattr(favicon_mod, "fetch_limited", _fetch_decode)
    assert favicon_mod.fetch_favicon("https://d/page") == (ico, ".ico")

    # Cover branch where link candidate exists but fetch returns None,
    # then favicon.ico exists but invalid bytes -> final None.
    html = b"<html><head><link rel='icon' href='/icon.ico'></head></html>"

    def _fetch_none(url: str, _limit: int):
        if url == "https://n/page":
            return ("https://n/page", "text/html", html)
        if url == "https://n/icon.ico":
            return None
        if url == "https://n/favicon.ico":
            return ("https://n/favicon.ico", "image/x-icon", b"bad")
        return None

    monkeypatch.setattr(favicon_mod, "fetch_limited", _fetch_none)
    assert favicon_mod.fetch_favicon("https://n/page") is None


def test_fetch_favicon_retries_without_www_once(monkeypatch) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    html = b"<html><head><link rel='icon' href='/icon.png'></head></html>"

    def _fetch_www(url: str, _limit: int):
        if url == "https://www.example.com/page":
            return None
        if url == "https://example.com/page":
            return ("https://example.com/page", "text/html", html)
        if url == "https://example.com/icon.png":
            return ("https://example.com/icon.png", "image/png", png)
        return None

    monkeypatch.setattr(favicon_mod, "fetch_limited", _fetch_www)
    assert favicon_mod.fetch_favicon("https://www.example.com/page") == (png, ".png")

