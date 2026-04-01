"""Tests for zap.py CLI/action paths not covered by core tests."""

from __future__ import annotations

import io
import json
import runpy
from pathlib import Path

import zap


def test_data_dir_from_env_relative_and_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(zap, "_DEFAULT_DATA_DIR", tmp_path / "default")
    monkeypatch.setenv("DATA_PATH", "")
    assert zap._data_dir_from_env() == tmp_path / "default"  # noqa: SLF001

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("DATA_PATH", "rel/path")
    assert zap._data_dir_from_env() == tmp_path / "rel/path"  # noqa: SLF001


def test_pick_open_web_port_in_range(monkeypatch) -> None:
    monkeypatch.setattr(zap, "_WEB_PORT_MIN", 14535)
    monkeypatch.setattr(zap, "_WEB_PORT_MAX", 14537)
    monkeypatch.setattr(zap.random, "shuffle", lambda _ports: None)

    class _Sock:
        attempts: list[int] = []

        def __init__(self, *_a, **_k) -> None:
            self.port = None

        def bind(self, addr) -> None:
            port = int(addr[1])
            self.port = port
            _Sock.attempts.append(port)
            if port in (14535, 14536):
                raise OSError("in use")

        def close(self) -> None:
            return None

    monkeypatch.setattr(zap.socket, "socket", lambda *_a, **_k: _Sock())
    assert zap._pick_open_web_port() == 14537  # noqa: SLF001
    assert _Sock.attempts == [14535, 14536, 14537]


def test_load_bookmarks_filters_invalid_and_bad_json(zap_module, tmp_path) -> None:
    (tmp_path / "zap.json").write_text(
        json.dumps(
            {
                "ok": {"url": " https://a.example ", "icon": 123},
                "bad1": {"url": ""},
                "bad2": "string",
                "bad3": {"url": None},
            }
        ),
        encoding="utf-8",
    )
    assert zap_module.load_bookmarks() == {"ok": {"url": "https://a.example", "icon": None}}

    (tmp_path / "zap.json").write_text("{broken", encoding="utf-8")
    assert zap_module.load_bookmarks() == {}

    (tmp_path / "zap.json").write_text("[]", encoding="utf-8")
    assert zap_module.load_bookmarks() == {}


def test_filename_and_icon_helpers(zap_module, tmp_path, monkeypatch) -> None:
    assert zap_module.sanitize_title_for_filename(' A:/B*?"C  ') == "A_B_C"

    monkeypatch.setattr(zap_module.secrets, "token_hex", lambda _n: "abc12345")
    assert zap_module.make_icon_filename("Title", ".png") == "Title_abc12345.png"

    assert zap_module.safe_icon_file_path(None) is None
    assert zap_module.safe_icon_file_path("../x.png") is None
    assert zap_module.safe_icon_file_path("a/b.png") is None
    ok = zap_module.safe_icon_file_path("ok.png")
    assert ok is not None and ok.name == "ok.png"

    zap_module.ensure_store()
    icon_file = zap_module.safe_icon_file_path("del.png")
    assert icon_file is not None
    icon_file.write_bytes(b"png")
    zap_module.remove_stored_icon("del.png")
    assert not icon_file.exists()

    import favicon as favicon_mod

    monkeypatch.setattr(favicon_mod, "fetch_favicon", lambda _u: (b"icon", ".exe"))
    saved_name = zap_module.fetch_and_store_icon("https://a", "A")
    assert saved_name is not None
    assert saved_name.endswith(".ico")
    assert (zap_module.ICON_DIR / saved_name).is_file()

    monkeypatch.setattr(favicon_mod, "fetch_favicon", lambda _u: None)
    assert zap_module.fetch_and_store_icon("https://a", "A") is None

    old_relative_to = Path.relative_to

    def _raise_relative_to(self, other):
        if str(self).endswith("bad.png"):
            raise ValueError("outside")
        return old_relative_to(self, other)

    monkeypatch.setattr(Path, "relative_to", _raise_relative_to)
    assert zap_module.safe_icon_file_path("bad.png") is None

    remove_target = zap_module.safe_icon_file_path("unlink-fail.png")
    assert remove_target is not None
    remove_target.write_bytes(b"x")
    monkeypatch.setattr(Path, "unlink", lambda self: (_ for _ in ()).throw(OSError("deny")))
    zap_module.remove_stored_icon("unlink-fail.png")


def test_default_icon_and_alfred_icon_payload(zap_module, monkeypatch, tmp_path) -> None:
    static = tmp_path / "web" / "static"
    static.mkdir(parents=True)
    static_icon = static / "zap-icon.png"
    static_icon.write_bytes(b"s")
    fallback_icon = tmp_path / "icon.png"
    fallback_icon.write_bytes(b"f")
    monkeypatch.setattr(zap_module, "__file__", str(tmp_path / "zap.py"))
    assert zap_module.default_bookmark_icon_path() == static_icon
    static_icon.unlink()
    assert zap_module.default_bookmark_icon_path() == fallback_icon

    payload_none = zap_module.alfred_icon_payload(None)
    assert payload_none["path"].endswith("icon.png")
    assert zap_module.alfred_icon_payload("a.svg")["path"].endswith("icon.png")
    assert zap_module.alfred_icon_payload("missing.png")["path"].endswith("icon.png")

    zap_module.ensure_store()
    existing = zap_module.safe_icon_file_path("ok.png")
    assert existing is not None
    existing.write_bytes(b"ok")
    payload = zap_module.alfred_icon_payload("ok.png")
    assert payload["path"].endswith("ok.png")


def test_run_osascript_prompt_and_confirm_paths(zap_module, monkeypatch) -> None:
    class _Result:
        def __init__(self, code: int, stdout: str) -> None:
            self.returncode = code
            self.stdout = stdout

    monkeypatch.setattr(zap_module.subprocess, "run", lambda *a, **k: _Result(0, " value \n"))
    assert zap_module.run_osascript("x") == "value"
    monkeypatch.setattr(zap_module.subprocess, "run", lambda *a, **k: _Result(1, ""))
    assert zap_module.run_osascript("x") == ""

    monkeypatch.setattr(zap_module, "run_osascript", lambda _s: "https://x")
    assert zap_module.prompt_for_url('My "Title"') == "https://x"
    monkeypatch.setattr(zap_module, "run_osascript", lambda _s: "")
    assert zap_module.prompt_for_url("My Title") is None
    monkeypatch.setattr(zap_module, "run_osascript", lambda _s: "Delete")
    assert zap_module.confirm_delete("A") is True
    monkeypatch.setattr(zap_module, "run_osascript", lambda _s: "Cancel")
    assert zap_module.confirm_delete("A") is False


def test_edit_and_delete_branches(zap_module, monkeypatch) -> None:
    assert zap_module.edit("", "https://x") == "Title is required."
    monkeypatch.setattr(zap_module, "prompt_for_url", lambda _t: None)
    assert zap_module.edit("A", None) == "Cancelled."

    monkeypatch.setattr(zap_module, "prompt_for_url", lambda _t: "example.com")
    monkeypatch.setattr(
        zap_module,
        "_schedule_icon_refresh",
        lambda title, url: zap_module._refresh_icon_for_bookmark(title, url),
    )
    monkeypatch.setattr(zap_module, "fetch_and_store_icon", lambda _u, _t: "n.png")
    assert zap_module.edit("A", None) == "Saved: A -> https://example.com"

    zap_module.save_bookmarks({"A": {"url": "https://a", "icon": "n.png"}})
    removed: list[str | None] = []
    monkeypatch.setattr(zap_module, "remove_stored_icon", lambda n: removed.append(n))
    monkeypatch.setattr(zap_module, "fetch_and_store_icon", lambda _u, _t: "m.png")
    assert zap_module.edit("A", "https://b") == "Saved: A -> https://b"
    assert "n.png" in removed

    assert zap_module.delete("") == "Title is required."
    assert zap_module.delete("Nope") == "Not found: Nope"
    monkeypatch.setattr(zap_module, "confirm_delete", lambda _t: False)
    assert zap_module.delete("A") == "Cancelled."
    monkeypatch.setattr(zap_module, "confirm_delete", lambda _t: True)
    assert zap_module.delete("A") == "Deleted: A"


def test_query_and_command_helpers(zap_module, monkeypatch) -> None:
    assert zap_module._normalize_query_whitespace(" \ufeffa\u00a0b\u2009c ") == "a b c"  # noqa: SLF001
    assert zap_module._command_key_from_token("еd!it") == "edit"  # noqa: SLF001

    out_edit = zap_module.script_filter_payload("edit MyTitle example.com")
    assert out_edit["items"][0]["arg"] == "edit::MyTitle::example.com"
    out_del = zap_module.script_filter_payload("del MyTitle")
    assert out_del["items"][0]["arg"] == "del::MyTitle"

    # leading "zap" alone
    out_zap = zap_module.script_filter_payload("zap")
    assert out_zap["items"][0]["valid"] is False

    monkeypatch.setattr(zap_module, "open_web", lambda: None)
    monkeypatch.setattr(zap_module, "edit", lambda t, u: f"EDIT:{t}:{u}")
    monkeypatch.setattr(zap_module, "delete", lambda t: f"DEL:{t}")
    assert zap_module.handle_action("web") == "Opened web."
    assert zap_module.handle_action("edit::A::") == "EDIT:A:None"
    assert zap_module.handle_action("del::A") == "DEL:A"
    assert zap_module.handle_action("x") == "Unknown action."


def test_script_filter_query_from_argv_and_stdin(monkeypatch) -> None:
    class _FakeStdin(io.StringIO):
        def __init__(self, value: str, is_tty: bool) -> None:
            super().__init__(value)
            self._is_tty = is_tty

        def isatty(self) -> bool:
            return self._is_tty

    assert zap._argv_query_tail(["zap.py", "--script-filter", "a", "b"], 2) == "a b"  # noqa: SLF001
    assert zap._script_filter_query_from_argv(["zap.py", "--script-filter", "x"]) == "x"  # noqa: SLF001

    monkeypatch.setattr(zap.sys, "stdin", _FakeStdin("from-stdin", is_tty=False))
    assert zap._script_filter_query_from_argv(["zap.py", "--script-filter"]) == "from-stdin"  # noqa: SLF001

    class _ErrStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            raise OSError("boom")

    monkeypatch.setattr(zap.sys, "stdin", _ErrStdin())
    assert zap._script_filter_query_from_argv(["zap.py", "--script-filter"]) == ""  # noqa: SLF001

    class _TtyStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(zap.sys, "stdin", _TtyStdin())
    assert zap._script_filter_query_from_argv(["zap.py", "--script-filter"]) == ""  # noqa: SLF001


def test_main_cli_branches(monkeypatch, capsys) -> None:
    monkeypatch.setattr(zap, "script_filter_payload", lambda q: {"items": [{"title": q}]})
    assert zap.main(["zap.py", "--script-filter", "abc"]) == 0
    assert json.loads(capsys.readouterr().out)["items"][0]["title"] == "abc"

    monkeypatch.setattr(zap, "handle_action", lambda arg: f"H:{arg}")
    assert zap.main(["zap.py", "--action", "edit::A::u"]) == 0
    assert "H:edit::A::u" in capsys.readouterr().out

    class _NoTtyStdin(io.StringIO):
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(zap.sys, "stdin", _NoTtyStdin("del::A"))
    assert zap.main(["zap.py", "--action"]) == 0
    assert "H:del::A" in capsys.readouterr().out

    class _BadStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            raise OSError("nope")

    monkeypatch.setattr(zap.sys, "stdin", _BadStdin())
    assert zap.main(["zap.py", "--action"]) == 0
    assert "H:" in capsys.readouterr().out

    assert zap.main(["zap.py"]) == 1
    assert "Usage: zap.py" in capsys.readouterr().out

    monkeypatch.setattr(zap, "edit", lambda t, u: f"E:{t}:{u}")
    assert zap.main(["zap.py", "edit", "T", "u"]) == 0
    assert "E:T:u" in capsys.readouterr().out

    monkeypatch.setattr(zap, "delete", lambda t: f"D:{t}")
    assert zap.main(["zap.py", "del", "T"]) == 0
    assert "D:T" in capsys.readouterr().out

    called: list[bool] = []
    monkeypatch.setattr(zap, "open_web", lambda: called.append(True))
    assert zap.main(["zap.py", "web"]) == 0
    assert called == [True]

    monkeypatch.setattr(zap, "search", lambda _q: [])
    assert zap.main(["zap.py", "query"]) == 0
    assert "No bookmark found." in capsys.readouterr().out

    monkeypatch.setattr(
        zap,
        "search",
        lambda _q: [{"title": "A", "subtitle": "https://a", "arg": "https://a", "valid": True, "icon": {}}],
    )
    assert zap.main(["zap.py", "A"]) == 0
    assert "A\thttps://a" in capsys.readouterr().out


def test_open_web_dispatches_to_web_server(monkeypatch) -> None:
    called: list[tuple[str, int]] = []

    def _serve(host: str, port: int) -> None:
        called.append((host, port))

    monkeypatch.setattr(zap, "_pick_open_web_port", lambda: 23456)
    import types

    fake_web_server = types.SimpleNamespace(serve_zap_web=_serve)
    monkeypatch.setitem(__import__("sys").modules, "web.server", fake_web_server)

    zap.open_web()
    assert called == [("127.0.0.1", 23456)]


def test_zap_dunder_main_executes_main(monkeypatch, capsys) -> None:
    monkeypatch.setattr(zap.sys, "argv", ["zap.py"])
    try:
        runpy.run_path(zap.__file__, run_name="__main__")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1
    assert "Usage: zap.py" in capsys.readouterr().out
