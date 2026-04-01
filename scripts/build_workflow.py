#!/usr/bin/env python3
import argparse
import compileall
import os
import plistlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

VERSION_THREE = re.compile(r"^\d+\.\d+\.\d+$")

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_TOML = ROOT / "pyproject.toml"
WORKFLOW_DIR = ROOT / "workflow"
DIST = ROOT / "dist"
README_NAME = "README.md"


def _dist_artifacts(channel: str) -> tuple[Path, Path, str]:
    """Paths for built workflow and shutil.make_archive stem (without .zip)."""
    if channel == "release":
        return DIST / "zap.alfredworkflow", DIST / "zap-workflow", "zap"
    if channel == "test":
        return DIST / "zap-test.alfredworkflow", DIST / "zap-test-workflow", "zap-test"
    raise ValueError(f"unknown channel: {channel!r}")

PLACEHOLDER_README = "__ZAP_README__"


def _deep_replace_placeholders(obj, mapping: dict[str, str]):
    if isinstance(obj, dict):
        return {k: _deep_replace_placeholders(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_replace_placeholders(v, mapping) for v in obj]
    if isinstance(obj, str) and obj in mapping:
        return mapping[obj]
    return obj


def _assert_no_zap_placeholders(obj) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_no_zap_placeholders(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_zap_placeholders(v)
    elif isinstance(obj, str) and obj.startswith("__ZAP_"):
        raise ValueError(f"Unresolved placeholder in plist: {obj!r}")


def _read_plist_version(plist_path: Path) -> str:
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    v = data.get("version", "0.0.0")
    return str(v).strip() if v is not None else "0.0.0"


def _version_from_pyproject_regex(text: str) -> str | None:
    in_project = False
    for line in text.splitlines():
        s = line.strip()
        if s == "[project]":
            in_project = True
            continue
        if s.startswith("[") and s.endswith("]"):
            in_project = False
            continue
        if in_project:
            m = re.match(r'version\s*=\s*"([^"]+)"\s*$', s)
            if m:
                return m.group(1)
    return None


def _read_release_version_from_pyproject() -> str:
    if not PYPROJECT_TOML.is_file():
        raise FileNotFoundError(f"Missing pyproject.toml: {PYPROJECT_TOML}")
    text = PYPROJECT_TOML.read_text(encoding="utf-8")
    ver: str | None = None
    try:
        import tomllib
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment, unused-ignore]
    if tomllib is not None:
        data = tomllib.loads(text)
        proj = data.get("project")
        if isinstance(proj, dict):
            v = proj.get("version")
            if v is not None:
                ver = str(v).strip()
    if ver is None:
        ver = _version_from_pyproject_regex(text)
    if not ver:
        raise ValueError(
            f"Could not read [project] version from {PYPROJECT_TOML}"
        )
    return _validate_version_three(ver)


def _suggest_next_version(current: str) -> str:
    """Pad to three numeric segments, increment the patch (last) segment."""
    parts: list[int] = []
    for p in current.strip().split("."):
        if not p.isdigit():
            parts = []
            break
        parts.append(int(p))
    if not parts:
        parts = [0, 0, 0]
    while len(parts) < 3:
        parts.append(0)
    parts = parts[:3]
    parts[2] += 1
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def _validate_version_three(v: str) -> str:
    v = v.strip()
    if not VERSION_THREE.fullmatch(v):
        raise ValueError(f"Version must match x.y.z (digits only), got {v!r}")
    return v


def _resolve_test_version(plist_path: Path, cli_version: str | None) -> str:
    current = _read_plist_version(plist_path)
    suggested = _suggest_next_version(current)

    if cli_version is not None:
        return _validate_version_three(cli_version)

    env_v = os.environ.get("ZAP_VERSION", "").strip()
    if env_v:
        return _validate_version_three(env_v)

    if not sys.stdin.isatty():
        return _validate_version_three(suggested)

    while True:
        try:
            line = input(f"Version [{suggested}]: ").strip()
        except EOFError:
            return _validate_version_three(suggested)
        chosen = line if line else suggested
        try:
            return _validate_version_three(chosen)
        except ValueError as e:
            print(f"{e}", file=sys.stderr)


def _resolve_build_version(
    plist_path: Path,
    channel: str,
    cli_version: str | None,
) -> str:
    if channel == "release":
        if cli_version is not None:
            raise SystemExit(
                "error: --version is not allowed with --channel release "
                "(release version comes from pyproject.toml [project] version)"
            )
        if os.environ.get("ZAP_VERSION", "").strip():
            print(
                "warning: ZAP_VERSION is ignored for --channel release",
                file=sys.stderr,
            )
        release_ver = _read_release_version_from_pyproject()
        plist_ver = _read_plist_version(plist_path)
        if plist_ver != release_ver:
            print(
                f"warning: workflow/info.plist version {plist_ver!r} != "
                f"pyproject.toml {release_ver!r} (using pyproject for this build)",
                file=sys.stderr,
            )
        return release_ver

    return _resolve_test_version(plist_path, cli_version)


def _write_source_plist_version_only(plist_path: Path, new_version: str) -> None:
    """Update only top-level workflow version; keep placeholders (e.g. __ZAP_README__)."""
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    data["version"] = new_version
    with open(plist_path, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_XML)


def _workflow_copy_ignore(src: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    base = Path(src).resolve()
    if base == WORKFLOW_DIR.resolve():
        ignored.update(
            n for n in names if n == "__pycache__" or n.endswith(".pyc")
        )
    return ignored


def build(
    version: str | None = None,
    channel: str = "test",
) -> tuple[Path, Path, str]:
    if not WORKFLOW_DIR.is_dir():
        raise FileNotFoundError(f"Missing workflow directory: {WORKFLOW_DIR}")
    plist_path = WORKFLOW_DIR / "info.plist"
    readme_path = WORKFLOW_DIR / README_NAME
    if not plist_path.is_file():
        raise FileNotFoundError(f"Missing workflow plist: {plist_path}")
    if not readme_path.is_file():
        raise FileNotFoundError(f"Missing workflow readme: {readme_path}")

    resolved_version = _resolve_build_version(plist_path, channel, version)

    readme_body = readme_path.read_text(encoding="utf-8").rstrip()
    mapping = {PLACEHOLDER_README: readme_body}

    with open(plist_path, "rb") as f:
        plist_data = plistlib.load(f)
    if plist_data.get("readme") != PLACEHOLDER_README:
        raise ValueError(
            f"info.plist readme must be exactly {PLACEHOLDER_README!r} in source; "
            f"got {plist_data.get('readme')!r}"
        )
    plist_data = _deep_replace_placeholders(plist_data, mapping)
    _assert_no_zap_placeholders(plist_data)
    plist_data["version"] = resolved_version

    workflow_zip, dist_unpacked, archive_stem = _dist_artifacts(channel)

    DIST.mkdir(parents=True, exist_ok=True)
    if dist_unpacked.exists():
        shutil.rmtree(dist_unpacked)
    workflow_zip.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "workflow"
        shutil.copytree(WORKFLOW_DIR, stage, ignore=_workflow_copy_ignore)
        bundled_icon = stage / "icon.png"
        static_icon = stage / "web" / "static" / "zap-icon.png"
        if bundled_icon.is_file():
            static_icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundled_icon, static_icon)
        staged_plist = stage / "info.plist"
        with open(staged_plist, "wb") as f:
            plistlib.dump(plist_data, f, fmt=plistlib.FMT_XML)

        compileall.compile_dir(str(stage), quiet=2, optimize=0)

        shutil.copytree(stage, dist_unpacked)

        out_base = DIST / archive_stem
        archive = shutil.make_archive(str(out_base), "zip", root_dir=stage)
        Path(archive).rename(workflow_zip)

    _write_source_plist_version_only(plist_path, resolved_version)

    return workflow_zip, dist_unpacked, resolved_version


def main() -> None:
    parser = argparse.ArgumentParser(description="Build zap.alfredworkflow.")
    parser.add_argument(
        "--channel",
        choices=("test", "release"),
        default="test",
        help="test: version from plist bump / prompt / ZAP_VERSION / --version. "
        "release: version from pyproject.toml [project] version only.",
    )
    parser.add_argument(
        "--version",
        default=None,
        metavar="X.Y.Z",
        help="(test channel only) Skips prompt; overrides ZAP_VERSION.",
    )
    args = parser.parse_args()
    wf_zip, wf_dir, ver = build(version=args.version, channel=args.channel)
    print(wf_zip)
    print(wf_dir)
    print(f"version={ver}", flush=True)
    print(f"channel={args.channel}", flush=True)


if __name__ == "__main__":
    main()
