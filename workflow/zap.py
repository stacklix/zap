#!/usr/bin/env python3
import json
import os
import re
import secrets
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE_FILENAME = "zap.json"
_ICON_SUBDIR = "icon"
_DEFAULT_DATA_DIR = Path("~/.config/alfred/zap").expanduser()
_DEFAULT_WEB_PORT = 14535


def _data_dir_from_env() -> Path:
    raw = os.environ.get("DATA_PATH", "").strip()
    if not raw:
        return _DEFAULT_DATA_DIR
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = Path.home() / p
    return p


def _web_port_from_env() -> int:
    raw = os.environ.get("WEB_PORT", "").strip()
    if not raw:
        return _DEFAULT_WEB_PORT
    try:
        n = int(raw, 10)
    except ValueError:
        return _DEFAULT_WEB_PORT
    if not (1 <= n <= 65535):
        return _DEFAULT_WEB_PORT
    return n


DATA_DIR = _data_dir_from_env()
BOOKMARKS_PATH = DATA_DIR / _STORE_FILENAME
ICON_DIR = DATA_DIR / _ICON_SUBDIR
WEB_PORT = _web_port_from_env()


def ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    if not BOOKMARKS_PATH.exists():
        BOOKMARKS_PATH.write_text("{}\n", encoding="utf-8")


def load_bookmarks() -> Dict[str, Dict[str, Any]]:
    ensure_store()
    try:
        raw = BOOKMARKS_PATH.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            url = v.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            icon = v.get("icon")
            if icon is not None and not isinstance(icon, str):
                icon = None
            out[str(k)] = {"url": url.strip(), "icon": icon}
        return out
    except Exception:
        pass
    return {}


def save_bookmarks(data: Dict[str, Dict[str, Any]]) -> None:
    ensure_store()
    payload: Dict[str, Dict[str, Any]] = {}
    for title in sorted(data.keys(), key=lambda t: t.lower()):
        v = data[title]
        entry: Dict[str, Any] = {"url": v["url"]}
        if v.get("icon"):
            entry["icon"] = v["icon"]
        payload[title] = entry
    BOOKMARKS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sanitize_title_for_filename(title: str) -> str:
    s = title.strip()
    for ch in '\\/:*?"<>|\n\r\t\x00':
        s = s.replace(ch, "_")
    s = re.sub(r"_+", "_", s).strip("._")
    return s[:80] if s else "bookmark"


def make_icon_filename(title: str, ext: str) -> str:
    base = sanitize_title_for_filename(title)
    return f"{base}_{secrets.token_hex(4)}{ext}"


def safe_icon_file_path(filename: Optional[str]) -> Optional[Path]:
    if not filename or not isinstance(filename, str):
        return None
    name = Path(filename).name
    if name != filename or ".." in filename:
        return None
    base = ICON_DIR.resolve()
    p = (base / name).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        return None
    return p


def remove_stored_icon(filename: Optional[str]) -> None:
    p = safe_icon_file_path(filename)
    if p is not None and p.is_file():
        try:
            p.unlink()
        except OSError:
            pass


def fetch_and_store_icon(page_url: str, title: str) -> Optional[str]:
    import favicon as site_favicon

    got = site_favicon.fetch_favicon(page_url)
    if not got:
        return None
    raw, ext = got
    if ext not in (".png", ".jpg", ".jpeg", ".ico", ".svg", ".webp"):
        ext = ".ico"
    ensure_store()
    name = make_icon_filename(title, ext)
    (ICON_DIR / name).write_bytes(raw)
    return name


def default_bookmark_icon_path() -> Path:
    static = Path(__file__).resolve().parent / "web" / "static" / "zap-icon.png"
    if static.is_file():
        return static
    fallback = Path(__file__).resolve().parent / "icon.png"
    return fallback


def alfred_icon_payload(stored_name: Optional[str]) -> Dict[str, str]:
    fb = default_bookmark_icon_path()
    fallback = {"path": str(fb), "type": ""}
    if not stored_name:
        return fallback
    if stored_name.lower().endswith(".svg"):
        return fallback
    ip = safe_icon_file_path(stored_name)
    if ip is None or not ip.is_file():
        return fallback
    return {"path": str(ip), "type": ""}


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def prompt_for_url(title: str) -> Optional[str]:
    safe_title = title.replace('"', '\\"')
    script = (
        'set d to display dialog "Input URL for: '
        + safe_title
        + '" default answer "" buttons {"Cancel", "Save"} default button "Save"\n'
        "if button returned of d is \"Save\" then return text returned of d"
    )
    url = run_osascript(script)
    return url.strip() if url else None


def confirm_delete(title: str) -> bool:
    safe_title = title.replace('"', '\\"')
    script = (
        'set d to display dialog "Delete bookmark: '
        + safe_title
        + ' ?" buttons {"Cancel", "Delete"} default button "Cancel"\n'
        'return button returned of d'
    )
    return run_osascript(script) == "Delete"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if "://" not in url:
        return "https://" + url
    return url


def search(title: str) -> List[dict]:
    data = load_bookmarks()
    q = title.lower().strip()
    rows = []
    for t, entry in data.items():
        u = entry["url"]
        if not q or q in t.lower() or q in u.lower():
            rows.append(
                {
                    "title": t,
                    "subtitle": u,
                    "arg": u,
                    "valid": True,
                    "icon": alfred_icon_payload(entry.get("icon")),
                }
            )
    rows.sort(key=lambda x: x["title"].lower())
    return rows


def edit(title: str, url: Optional[str]) -> str:
    title = title.strip()
    if not title:
        return "Title is required."

    if not url:
        url = prompt_for_url(title)
    if not url:
        return "Cancelled."

    url = normalize_url(url)
    data = load_bookmarks()
    prev = data.get(title)
    if prev:
        remove_stored_icon(prev.get("icon"))
    icon = fetch_and_store_icon(url, title)
    data[title] = {"url": url, "icon": icon}
    save_bookmarks(data)
    return f"Saved: {title} -> {url}"


def delete(title: str) -> str:
    title = title.strip()
    if not title:
        return "Title is required."
    data = load_bookmarks()
    if title not in data:
        return f"Not found: {title}"
    if not confirm_delete(title):
        return "Cancelled."
    remove_stored_icon(data[title].get("icon"))
    del data[title]
    save_bookmarks(data)
    return f"Deleted: {title}"


def open_web() -> None:
    from web.server import serve_zap_web

    serve_zap_web("127.0.0.1", WEB_PORT)


def _normalize_query_whitespace(query: str) -> str:
    """Collapse whitespace; replace NBSP and thin spaces so partition/split behave."""
    s = query.replace("\ufeff", "").strip()
    s = unicodedata.normalize("NFKC", s)
    for ch in ("\u00a0", "\u2009", "\u202f", "\u2007", "\u2008"):
        s = s.replace(ch, " ")
    return " ".join(s.split())


# Cyrillic letters that look like Latin (IME / wrong layout) — keep "edit"/"del"/"web" recognizable.
_CYRILLIC_LOOKALIKE_TO_LATIN = str.maketrans(
    {
        "\u0430": "a",  # а
        "\u0435": "e",  # е
        "\u043e": "o",  # о
        "\u0440": "p",  # р
        "\u0441": "c",  # с
        "\u0443": "y",  # у
        "\u0445": "x",  # х
        "\u0456": "i",  # і
        "\u0458": "j",  # ј
    }
)


def _command_key_from_token(command_token: str) -> str:
    t = command_token.lower().translate(_CYRILLIC_LOOKALIKE_TO_LATIN)
    return re.sub(r"[^a-z]", "", t)


def script_filter_payload(query: str) -> dict:
    q = _normalize_query_whitespace(query)
    parts = q.split()
    if not parts:
        return {
            "items": [
                {
                    "title": "Type to search",
                    "subtitle": "Or: edit | del | web",
                    "valid": False,
                }
            ]
        }
    # Some Alfred setups pass "zap …" inside {query}; strip leading zap token.
    if parts[0].lower() == "zap":
        parts = parts[1:]
        if not parts:
            return {
                "items": [
                    {
                        "title": "zap",
                        "subtitle": "Search, or use edit / del / web",
                        "valid": False,
                    }
                ]
            }
    command_token = parts[0]
    rest_parts = parts[1:]
    command = _command_key_from_token(command_token)

    if command == "web":
        return {
            "items": [
                {
                    "title": "Open zap web UI",
                    "subtitle": "Manage bookmarks in browser",
                    "arg": "web",
                    "valid": True,
                }
            ]
        }

    if command == "edit":
        title = rest_parts[0].strip() if rest_parts else ""
        url = " ".join(rest_parts[1:]).strip() if len(rest_parts) > 1 else ""
        return {
            "items": [
                {
                    "title": f"Add or edit: {title}",
                    "subtitle": f'URL: {url or "(ask in dialog)"}',
                    "arg": f"edit::{title}::{url}",
                    "valid": bool(title),
                }
            ]
        }

    if command == "del":
        title = " ".join(rest_parts).strip()
        return {
            "items": [
                {
                    "title": f"Delete: {title}",
                    "subtitle": "Will ask for confirmation",
                    "arg": f"del::{title}",
                    "valid": bool(title),
                }
            ]
        }

    items = search(q)
    if not items:
        items = [
            {
                "title": "No bookmark found",
                "subtitle": "Try: zap edit <title> <url>",
                "valid": False,
            }
        ]
    return {"items": items}


def handle_action(action_arg: str) -> str:
    if action_arg == "web":
        open_web()
        return "Opened web."
    if action_arg.startswith("edit::"):
        _, title, url = action_arg.split("::", 2)
        return edit(title, url or None)
    if action_arg.startswith("del::"):
        _, title = action_arg.split("::", 1)
        return delete(title)
    return "Unknown action."


def _argv_query_tail(argv: List[str], start: int) -> str:
    """Join argv from start onward (Alfred/zsh often split {query} on spaces if unquoted)."""
    return " ".join(argv[start:]).strip()


def _script_filter_query_from_argv(argv: List[str]) -> str:
    """Alfred may pass {query} as argv tail, on stdin, or both; handle all common cases."""
    q = _argv_query_tail(argv, 2)
    if q:
        return q
    if not sys.stdin.isatty():
        try:
            stdin_q = sys.stdin.read()
        except OSError:
            stdin_q = ""
        return stdin_q.strip()
    return ""


def main(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--script-filter":
        q = _script_filter_query_from_argv(argv)
        print(json.dumps(script_filter_payload(q), ensure_ascii=False))
        return 0
    if len(argv) >= 2 and argv[1] == "--action":
        arg = _argv_query_tail(argv, 2)
        if not arg and not sys.stdin.isatty():
            try:
                arg = sys.stdin.read().strip()
            except OSError:
                arg = ""
        print(handle_action(arg))
        return 0

    if len(argv) < 2:
        print("Usage: zap.py <title|edit|del|web> ...")
        return 1

    cmd = argv[1]
    if cmd == "edit":
        title = argv[2] if len(argv) >= 3 else ""
        url = argv[3] if len(argv) >= 4 else None
        print(edit(title, url))
        return 0
    if cmd == "del":
        title = argv[2] if len(argv) >= 3 else ""
        print(delete(title))
        return 0
    if cmd == "web":
        open_web()
        return 0

    q = " ".join(argv[1:])
    rows = search(q)
    if not rows:
        print("No bookmark found.")
        return 0
    for row in rows:
        print(f'{row["title"]}\t{row["subtitle"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
