"""Tests for web.server HTTP handlers and lifecycle helpers."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import web.server as web_server


def _request(port: int, method: str, path: str, body: str | None = None) -> tuple[int, dict, bytes]:
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {}
    raw_body = None
    if body is not None:
        raw_body = body.encode("utf-8")
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=raw_body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    out_headers = {k: v for (k, v) in resp.getheaders()}
    status = resp.status
    conn.close()
    return status, out_headers, data


def _start_server() -> tuple[object, threading.Thread, int]:
    server = web_server.HTTPServer(("127.0.0.1", 0), web_server.ZapWebHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, int(server.server_address[1])


def test_safe_static_path_blocks_traversal(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app_js = static_dir / "app.js"
    app_js.write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static_dir)

    assert web_server._safe_static_path("/static/app.js") == app_js
    assert web_server._safe_static_path("/static/../secret.txt") is None
    assert web_server._safe_static_path("/static/") is None
    assert web_server._safe_static_path("/api/ping") is None


def test_icon_file_priority(monkeypatch, tmp_path) -> None:
    workflow_icon = tmp_path / "icon.png"
    static_icon = tmp_path / "zap-icon.png"
    monkeypatch.setattr(web_server, "WORKFLOW_ICON", workflow_icon)
    monkeypatch.setattr(web_server, "STATIC_ICON", static_icon)

    assert web_server._icon_file() is None
    static_icon.write_bytes(b"s")
    assert web_server._icon_file() == static_icon
    workflow_icon.write_bytes(b"w")
    assert web_server._icon_file() == workflow_icon


def test_http_endpoints_and_handlers(monkeypatch, tmp_path, zap_module) -> None:
    # Wire server to isolated zap module instance backed by tmp_path.
    monkeypatch.setattr(web_server, "zap", zap_module)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    (static_dir / "app.js").write_text("console.log('js')", encoding="utf-8")
    (static_dir / "styles.css").write_text("body{margin:0}", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static_dir)

    workflow_icon = tmp_path / "icon.png"
    workflow_icon.write_bytes(b"\x89PNGworkflow")
    static_icon = static_dir / "zap-icon.png"
    static_icon.write_bytes(b"\x89PNGstatic")
    monkeypatch.setattr(web_server, "WORKFLOW_ICON", workflow_icon)
    monkeypatch.setattr(web_server, "STATIC_ICON", static_icon)

    default_icon = tmp_path / "default.png"
    default_icon.write_bytes(b"\x89PNGdefault")
    monkeypatch.setattr(zap_module, "default_bookmark_icon_path", lambda: default_icon)

    removed_icons: list[str | None] = []
    original_remove_stored_icon = zap_module.remove_stored_icon

    def _remove_icon(name):
        removed_icons.append(name)
        original_remove_stored_icon(name)

    monkeypatch.setattr(zap_module, "remove_stored_icon", _remove_icon)
    monkeypatch.setattr(zap_module, "fetch_and_store_icon", lambda *_: "fetched.png")

    # Prepare one bookmark with icon file and one without.
    zap_module.ensure_store()
    icon_file = zap_module.safe_icon_file_path("site.svg")
    assert icon_file is not None
    icon_file.write_text("<svg></svg>", encoding="utf-8")
    zap_module.save_bookmarks(
        {
            "Alpha": {"url": "https://alpha.example", "icon": "site.svg"},
            "Beta": {"url": "https://beta.example", "icon": None},
        }
    )

    server, thread, port = _start_server()
    try:
        status, headers, body = _request(port, "GET", "/")
        assert status == 200
        assert "text/html" in headers["Content-Type"]
        assert b"ok" in body

        status, headers, body = _request(port, "GET", "/static/app.js")
        assert status == 200
        assert headers["Content-Type"] == "text/javascript; charset=utf-8"
        assert b"console.log" in body

        status, headers, body = _request(port, "GET", "/static/styles.css")
        assert status == 200
        assert headers["Content-Type"] == "text/css; charset=utf-8"
        assert b"margin" in body

        status, _, body = _request(port, "GET", "/api/ping")
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"ok": True}

        status, _, body = _request(port, "GET", "/api/bookmarks?q=alp")
        assert status == 200
        items = json.loads(body.decode("utf-8"))
        assert len(items) == 1
        assert items[0]["title"] == "Alpha"
        assert items[0]["iconUrl"] == "/api/icons/site.svg"

        status, headers, body = _request(port, "GET", "/api/icons/site.svg")
        assert status == 200
        assert headers["Content-Type"] == "image/svg+xml"
        assert b"<svg" in body

        status, headers, body = _request(port, "GET", "/api/icons/missing.png")
        assert status == 200
        assert headers["Content-Type"] == "image/png"
        assert b"default" in body

        status, headers, body = _request(port, "GET", "/zap-icon.png")
        assert status == 200
        assert headers["Content-Type"] == "image/png"
        assert b"workflow" in body

        status, _, body = _request(port, "GET", "/unknown")
        assert status == 404
        assert json.loads(body.decode("utf-8")) == {"error": "not found"}

        status, _, body = _request(port, "POST", "/api/ping", "{}")
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"ok": True}

        status, _, body = _request(port, "POST", "/api/bookmarks", "{bad-json")
        assert status == 400
        assert json.loads(body.decode("utf-8")) == {"error": "invalid json"}

        status, _, body = _request(port, "POST", "/api/other", "{}")
        assert status == 404
        assert json.loads(body.decode("utf-8")) == {"error": "not found"}

        status, _, body = _request(port, "POST", "/api/bookmarks", json.dumps({"url": "example.com"}))
        assert status == 400
        assert json.loads(body.decode("utf-8")) == {"error": "title required"}

        status, _, body = _request(port, "POST", "/api/bookmarks", json.dumps({"title": "Gamma"}))
        assert status == 400
        assert json.loads(body.decode("utf-8")) == {"error": "url required"}

        status, _, body = _request(
            port,
            "POST",
            "/api/bookmarks",
            json.dumps({"title": "Alpha", "url": "gamma.example"}),
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload == {"ok": True, "icon": "fetched.png"}
        saved = zap_module.load_bookmarks()
        assert saved["Alpha"]["url"] == "https://gamma.example"
        assert saved["Alpha"]["icon"] == "fetched.png"
        assert "site.svg" in removed_icons

        status, _, body = _request(port, "DELETE", "/api/bookmarks/Alpha")
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"ok": True}
        assert "Alpha" not in zap_module.load_bookmarks()
        assert "fetched.png" in removed_icons

        status, _, body = _request(port, "DELETE", "/api/bookmarks/DoesNotExist")
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"ok": True}

        status, _, body = _request(port, "DELETE", "/api/unknown")
        assert status == 404
        assert json.loads(body.decode("utf-8")) == {"error": "not found"}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_root_returns_404_when_index_missing(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    monkeypatch.setattr(web_server, "STATIC_DIR", static_dir)

    server, thread, port = _start_server()
    try:
        status, _, body = _request(port, "GET", "/")
        assert status == 404
        payload = json.loads(body.decode("utf-8"))
        assert payload["error"] == "index missing"
        assert "index.html" in payload["path"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_icon_endpoint_404_without_any_icon(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static_dir)

    missing_workflow_icon = tmp_path / "missing-workflow-icon.png"
    missing_static_icon = tmp_path / "missing-static-icon.png"
    monkeypatch.setattr(web_server, "WORKFLOW_ICON", missing_workflow_icon)
    monkeypatch.setattr(web_server, "STATIC_ICON", missing_static_icon)

    server, thread, port = _start_server()
    try:
        status, _, body = _request(port, "GET", "/zap-icon.png")
        assert status == 404
        assert json.loads(body.decode("utf-8")) == {"error": "not found"}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_open_browser_tolerates_oserror(monkeypatch) -> None:
    def _boom(*_, **__):
        raise OSError("no open command")

    monkeypatch.setattr(web_server.subprocess, "run", _boom)
    web_server.open_browser("http://127.0.0.1:14535")


def test_idle_watch_loop_shutdown_paths(monkeypatch) -> None:
    class _Server:
        def __init__(self) -> None:
            self.called = 0

        def shutdown(self) -> None:
            self.called += 1

    srv = _Server()
    monkeypatch.setattr(web_server, "_http_server", srv)
    monkeypatch.setattr(web_server, "_last_ping_monotonic", 0.0)
    monkeypatch.setattr(web_server, "_IDLE_AFTER_SECONDS", 1.0)
    monkeypatch.setattr(web_server.time, "sleep", lambda _n: None)
    monkeypatch.setattr(web_server.time, "monotonic", lambda: 10.0)

    web_server._idle_watch_loop()
    assert srv.called == 1

    class _BrokenServer:
        def shutdown(self) -> None:
            raise OSError("already closed")

    monkeypatch.setattr(web_server, "_http_server", _BrokenServer())
    monkeypatch.setattr(web_server, "_last_ping_monotonic", 0.0)
    web_server._idle_watch_loop()


def test_serve_zap_web_bootstraps_server(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static_dir)

    opened: list[str] = []
    monkeypatch.setattr(web_server, "open_browser", lambda url: opened.append(url))

    class _FakeServer:
        def __init__(self, bind: tuple[str, int], _handler) -> None:
            self.bind = bind

        def serve_forever(self) -> None:
            return

    class _FakeThread:
        def __init__(self, target, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False

        def start(self) -> None:
            self.started = True

    monkeypatch.setattr(web_server, "HTTPServer", _FakeServer)
    monkeypatch.setattr(web_server.threading, "Thread", _FakeThread)

    web_server.serve_zap_web("127.0.0.1", 19999)

    assert opened == ["http://127.0.0.1:19999"]
    assert web_server._http_server is None
    assert web_server._last_ping_monotonic > 0
