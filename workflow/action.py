#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PYTHON_BIN = "/usr/bin/python3"


def _open_url(url: str) -> int:
    # Prefer macOS open first.
    try:
        proc = subprocess.run(["open", url], check=False)
        if proc.returncode == 0:
            return 0
    except OSError:
        pass

    # Fallback: AppleScript can open URLs even when `open` is flaky.
    safe_url = url.replace("\\", "\\\\").replace('"', '\\"')
    script = f'open location "{safe_url}"'
    try:
        proc = subprocess.run(["osascript", "-e", script], check=False)
        if proc.returncode == 0:
            return 0
    except OSError:
        pass

    print(f"Failed to open URL: {url}")
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print("Missing action arg")
        return 1
    arg = " ".join(sys.argv[1:]).strip()
    parsed = urlparse(arg)
    if parsed.scheme in {"http", "https"}:
        return _open_url(arg)
    script = str(Path(__file__).with_name("zap.py"))
    if arg == "web":
        try:
            subprocess.Popen(  # noqa: S603
                [PYTHON_BIN, script, "web"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
            print("Opened web.")
            return 0
        except OSError as e:
            print(f"Open web failed: {e}")
            return 1
    try:
        proc = subprocess.run([PYTHON_BIN, script, "--action", arg], check=False)
        return proc.returncode
    except OSError as e:
        print(f"Action runner failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
