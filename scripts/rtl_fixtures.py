"""Install verified external RTL fixtures without modifying existing checkouts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile

LOCK = Path(__file__).with_name("rtl-fixtures.lock.json")
DESTINATIONS = {
    "alexforencich/verilog-axis": "upstream_unknown/verilog-axis",
    "ZipCPU/wbuart32": "upstream_unknown/wbuart32",
    "openhwfoundation/cv32e40p": "upstream_cv32e40p",
    "openhwfoundation/cva6": "upstream_cva6",
}


class FixtureError(ValueError):
    pass


def load_lock(path=LOCK):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("repositories"), list):
        raise FixtureError("Invalid RTL fixture lock")
    seen = set()
    for entry in data["repositories"]:
        repo = entry.get("repository")
        if repo not in DESTINATIONS or repo in seen or entry.get("destination") != DESTINATIONS[repo]:
            raise FixtureError("Unknown or repeated fixture repository/destination")
        seen.add(repo)
        if not re.fullmatch(r"[0-9a-f]{40}", str(entry.get("commit", ""))):
            raise FixtureError("Invalid commit pin")
        blobs = entry.get("blobs")
        if not isinstance(blobs, dict) or not blobs:
            raise FixtureError("Missing blob pins")
        for name, sha in blobs.items():
            p = PurePosixPath(name)
            if (p.is_absolute() or str(p) != name or not p.parts or
                any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) for part in p.parts)
                or not re.fullmatch(r"[0-9a-f]{40}", str(sha))):
                raise FixtureError("Unsafe fixture path or invalid blob pin")
    if seen != set(DESTINATIONS):
        raise FixtureError("Incomplete RTL fixture lock")
    return data["repositories"]


def git(directory, *args, network=False):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_NO_LAZY_FETCH="0" if network else "1")
    # Do not accidentally operate on another repository via inherited overrides.
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    proc = subprocess.run(["git", "-c", "core.hooksPath=/dev/null",
                           "-C", str(directory), *args], env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if proc.returncode:
        raise FixtureError(f"git {args[0]} failed in {directory}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def safe_path(root, relative):
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise FixtureError(f"Symlink refused: {path}")
    return path


def blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def verify_checkout(directory, entry):
    if not directory.is_dir() or directory.is_symlink():
        raise FixtureError(f"Missing checkout: {directory}")
    if Path(git(directory, "rev-parse", "--show-toplevel")).resolve() != directory.resolve():
        raise FixtureError(f"Not a standalone checkout: {directory}")
    url = git(directory, "remote", "get-url", "origin")
    expected = "https://github.com/" + entry["repository"]
    if url not in (expected, expected + ".git"):
        raise FixtureError(f"Unexpected origin in {directory}: {url}")
    if git(directory, "rev-parse", "HEAD") != entry["commit"]:
        raise FixtureError(f"Wrong revision in {directory}; expected {entry['commit']}; existing checkout untouched")
    if git(directory, "status", "--porcelain=v1", "--untracked-files=all"):
        raise FixtureError(f"Dirty checkout: {directory}; existing checkout untouched")
    missing = []
    for name, sha in entry["blobs"].items():
        path = safe_path(directory, name)
        if not path.is_file():
            missing.append(name)
            continue
        if blob_sha(path) != sha or git(directory, "rev-parse", "HEAD:" + name) != sha:
            raise FixtureError(f"Blob mismatch: {path}")
    if missing:
        raise FixtureError(f"Missing pinned files in {directory}: {', '.join(missing)}; "
                           "existing checkout untouched; review sparse-checkout and add missing paths manually")


def install_checkout(directory, entry):
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".rtlprep-fixture-", dir=directory.parent) as tmp:
        stage = Path(tmp) / "checkout"
        stage.mkdir()
        git(stage, "init", "--quiet")
        git(stage, "remote", "add", "origin", "https://github.com/" + entry["repository"] + ".git")
        # Fetch exactly the reviewed commit, not a branch or a floating tag.
        git(stage, "fetch", "--no-tags", "--depth=1", "--no-recurse-submodules",
            "origin", entry["commit"], network=True)
        git(stage, "sparse-checkout", "set", "--no-cone",
            *("/" + p for p in entry["blobs"]))
        git(stage, "checkout", "--detach", entry["commit"])
        verify_checkout(stage, entry)
        if directory.exists() or directory.is_symlink():
            raise FixtureError(f"Destination appeared during installation: {directory}")
        stage.rename(directory)


def run(root, *, install=False, entries=None):
    root = root.resolve()
    entries = load_lock() if entries is None else entries
    if shutil.which("git") is None:
        raise FixtureError("Git is required")
    errors, absent, verified = [], [], []
    # Preflight all existing checkouts before any downloads or writes.
    for entry in entries:
        try:
            directory = safe_path(root, entry["destination"])
            if not directory.exists():
                absent.append((directory, entry))
            else:
                verify_checkout(directory, entry)
                verified.append(directory)
        except FixtureError as exc:
            errors.append(str(exc))
    for directory in verified:
        print(f"Verified: {directory}")
    if errors:
        raise FixtureError("\n".join(errors))
    if not install and absent:
        raise FixtureError("Missing checkouts: " + ", ".join(str(p) for p, _ in absent))
    for directory, entry in absent:
        install_checkout(directory, entry)
        print(f"Installed and verified: {directory}")
    print(f"RTL fixtures verified: {len(entries)}/{len(entries)} repositories; "
          f"{sum(len(e['blobs']) for e in entries)} pinned files")
    return 0
