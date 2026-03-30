"""HTTP server for Zap web UI: serves /static/* and JSON API."""

from __future__ import annotations

import json
import mimetypes
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import zap

# Anchor assets to the workflow folder that owns zap.py — not to this file's directory.
# Otherwise a different `web` package earlier on PYTHONPATH can shadow this module and
# STATIC_DIR would point at a tree with no `static/index.html`.
_WORKFLOW_ROOT = Path(zap.__file__).resolve().parent
STATIC_DIR = _WORKFLOW_ROOT / "web" / "static"
WORKFLOW_DIR = _WORKFLOW_ROOT
WORKFLOW_ICON = WORKFLOW_DIR / "icon.png"
STATIC_ICON = STATIC_DIR / "zap-icon.png"


def _icon_file() -> Path | None:
    if WORKFLOW_ICON.is_file():
        return WORKFLOW_ICON
    if STATIC_ICON.is_file():
        return STATIC_ICON
    return None

# Shut down when no browser tab has sent /api/ping for this long (seconds).
_IDLE_AFTER_SECONDS = 32.0
_idle_lock = threading.Lock()
_last_ping_monotonic: float = 0.0
_http_server: HTTPServer | None = None


def _mark_ping() -> None:
    global _last_ping_monotonic
    with _idle_lock:
        _last_ping_monotonic = time.monotonic()


def _idle_watch_loop() -> None:
    while True:
        time.sleep(5.0)
        with _idle_lock:
            if _http_server is None:
                return
            if time.monotonic() - _last_ping_monotonic < _IDLE_AFTER_SECONDS:
                continue
            srv = _http_server
        print("Zap web stopped: no active tab heartbeat for ~32s.", flush=True)
        try:
            srv.shutdown()
        except OSError:
            pass
        break


def _safe_static_path(url_path: str) -> Path | None:
    """Map /static/... to a file under STATIC_DIR; reject traversal."""
    if not url_path.startswith("/static/"):
        return None
    rel = url_path.removeprefix("/static/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    candidate = (STATIC_DIR / rel).resolve()
    try:
        candidate.relative_to(STATIC_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


class ZapWebHandler(BaseHTTPRequestHandler):
    def _send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            _mark_ping()
            index = STATIC_DIR / "index.html"
            if index.is_file():
                self._send_file(index, "text/html; charset=utf-8")
            else:
                self._json(
                    {
                        "error": "index missing",
                        "path": str(index),
                    },
                    404,
                )
            return

        if path == "/zap-icon.png":
            _mark_ping()
            icon = _icon_file()
            if icon is not None:
                self._send_file(icon, "image/png")
            else:
                self._json({"error": "not found"}, 404)
            return

        static_file = _safe_static_path(path)
        if static_file is not None:
            _mark_ping()
            ctype = mimetypes.guess_type(str(static_file))[0] or "application/octet-stream"
            if static_file.suffix == ".js":
                ctype = "text/javascript; charset=utf-8"
            elif static_file.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            self._send_file(static_file, ctype)
            return

        if path == "/api/ping":
            _mark_ping()
            self._json({"ok": True})
            return

        if path == "/api/bookmarks":
            _mark_ping()
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].lower()
            data = zap.load_bookmarks()
            items = []
            for k, v in sorted(data.items(), key=lambda i: i[0].lower()):
                if q and q not in k.lower() and q not in v["url"].lower():
                    continue
                icon = v.get("icon")
                icon_url = (
                    "/api/icons/" + urllib.parse.quote(icon, safe="")
                    if icon
                    else None
                )
                items.append({"title": k, "url": v["url"], "iconUrl": icon_url})
            self._json(items)
            return

        if path.startswith("/api/icons/"):
            _mark_ping()
            name = urllib.parse.unquote(path.removeprefix("/api/icons/").lstrip("/"))
            target = zap.safe_icon_file_path(name)
            default = zap.default_bookmark_icon_path()
            if target is None or not target.is_file():
                if default.is_file():
                    self._send_file(default, "image/png")
                else:
                    self._json({"error": "not found"}, 404)
                return
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if target.suffix.lower() == ".svg":
                ctype = "image/svg+xml"
            self._send_file(target, ctype)
            return

        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/ping":
            _mark_ping()
            self._json({"ok": True})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._json({"error": "invalid json"}, 400)
            return

        if path != "/api/bookmarks":
            self._json({"error": "not found"}, 404)
            return

        _mark_ping()
        title = str(payload.get("title", "")).strip()
        url = zap.normalize_url(str(payload.get("url", "")).strip())
        if not title:
            self._json({"error": "title required"}, 400)
            return
        if not url:
            self._json({"error": "url required"}, 400)
            return
        data = zap.load_bookmarks()
        if title in data:
            zap.remove_stored_icon(data[title].get("icon"))
        icon = zap.fetch_and_store_icon(url, title)
        data[title] = {"url": url, "icon": icon}
        zap.save_bookmarks(data)
        self._json({"ok": True, "icon": icon})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/bookmarks/"):
            self._json({"error": "not found"}, 404)
            return
        _mark_ping()
        title = urllib.parse.unquote(path.removeprefix("/api/bookmarks/")).strip()
        data = zap.load_bookmarks()
        if title in data:
            zap.remove_stored_icon(data[title].get("icon"))
            del data[title]
            zap.save_bookmarks(data)
        self._json({"ok": True})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def open_browser(url: str) -> None:
    try:
        subprocess.run(["open", url], check=False)
    except OSError:
        pass


def serve_zap_web(host: str, port: int) -> None:
    global _http_server, _last_ping_monotonic
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        print(f"Zap web UI: expected index at {index}", flush=True)
    url = f"http://{host}:{port}"
    open_browser(url)
    with _idle_lock:
        _last_ping_monotonic = time.monotonic()
    server = HTTPServer((host, port), ZapWebHandler)
    with _idle_lock:
        _http_server = server
    watcher = threading.Thread(target=_idle_watch_loop, name="zap-idle-watch", daemon=True)
    watcher.start()
    try:
        server.serve_forever()
    finally:
        with _idle_lock:
            _http_server = None
