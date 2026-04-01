# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Zap is an Alfred workflow bookmark manager with a local web UI. Dev dependencies are `pytest` and `taskipy`.

### Commands

| Task | Command |
|------|---------|
| Create venv | `python3 -m venv .venv` |
| Install dev deps | `./.venv/bin/python -m pip install -e ".[dev]"` |
| Run tests | `./.venv/bin/python -m pytest -q` |
| Build (test channel) | `python3 scripts/build_workflow.py --channel test --version <x.y.z>` |
| Build (release) | `make release` |

No linter is configured. CI (`.github/workflows/ci.yml`) runs only `pytest`.

### Mandatory workflow rules

- Use the project virtual environment (`.venv`) for development and all test runs.
- Prefer `./.venv/bin/python -m ...` form to avoid interpreter/path mismatch.
- Before committing code, run CI-equivalent tests locally and ensure they pass (`./.venv/bin/python -m pytest -q`).
- Do not create a commit when local tests are failing.

### Commit checklist

1. `python3 -m venv .venv` (if missing)
2. `./.venv/bin/python -m pip install -e ".[dev]"`
3. `./.venv/bin/python -m pytest -q`
4. Only then run `git add` + `git commit`

### Running the web UI

The web server starts via `cd workflow && python3 zap.py web`. It picks a free local port randomly in `14535..15000` on each run. The server auto-shuts down ~32 s after the last browser heartbeat.

Set `DATA_PATH` env var to use a custom bookmark store location (default `~/.config/alfred/zap/`).

### Gotchas

- `python` is not on PATH in this environment; always use `python3`.
- pip installs to `~/.local/bin`; ensure `PATH` includes it (`export PATH="$HOME/.local/bin:$PATH"`) before running `pytest` or `task` directly. Alternatively, invoke via `python3 -m pytest`.
- The `open` command (macOS) is not available on Linux; `zap.py web` will print the URL but won't auto-open a browser. Navigate manually.
- The build script's test channel prompts for a version interactively unless you pass `--version` or set `ZAP_VERSION`.
