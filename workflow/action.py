#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def main() -> int:
    if len(sys.argv) < 2:
        print("Missing action arg")
        return 1
    arg = " ".join(sys.argv[1:]).strip()
    parsed = urlparse(arg)
    if parsed.scheme in {"http", "https"}:
        subprocess.run(["open", arg], check=False)
        return 0
    script = str(Path(__file__).with_name("zap.py"))
    proc = subprocess.run(["python3", script, "--action", arg], check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
