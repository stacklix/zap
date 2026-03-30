# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Zap is an Alfred workflow bookmark manager with a local web UI. Dev dependencies are `pytest` and `taskipy`.

### Commands

| Task | Command |
|------|---------|
| Install dev deps | `python3 -m pip install -e ".[dev]"` |
| Run tests | `python3 -m pytest -q` |
| Build (test channel) | `python3 scripts/build_workflow.py --channel test --version <x.y.z>` |
| Build (release) | `make release` |

No linter is configured. CI (`.github/workflows/ci.yml`) runs only `pytest`.

### Running the web UI

The web server starts via `cd workflow && python3 zap.py web`. It binds to `127.0.0.1:14535` by default (override with `WEB_PORT` env var). The server auto-shuts down ~32 s after the last browser heartbeat.

Set `DATA_PATH` env var to use a custom bookmark store location (default `~/.config/alfred/zap/`).

### Gotchas

- `python` is not on PATH in this environment; always use `python3`.
- pip installs to `~/.local/bin`; ensure `PATH` includes it (`export PATH="$HOME/.local/bin:$PATH"`) before running `pytest` or `task` directly. Alternatively, invoke via `python3 -m pytest`.
- The `open` command (macOS) is not available on Linux; `zap.py web` will print the URL but won't auto-open a browser. Navigate manually.
- The build script's test channel prompts for a version interactively unless you pass `--version` or set `ZAP_VERSION`.
