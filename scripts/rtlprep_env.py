#!/usr/bin/env python3
"""RTLPrep development environment bootstrap for Linux x86_64 / WSL Debian.

No mutation by default. --install / --update use only checked-in, SHA256 pinned
vendor archives and the project's Python extras. No sudo or shell profile edit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import posixpath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK = Path(__file__).with_name("toolchain.lock.json")
BASE = Path.home() / ".local" / "share" / "rtlprep" / "toolchains"
MAX_MEMBERS = 150000
MAX_EXTRACTED_BYTES = 10 * 1024**3


class BootstrapError(Exception):
    """Installation refused or unsupported environment."""


def load_lock(path: Path = LOCK) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1 or lock.get("platform") != "linux-x86_64":
        raise BootstrapError("Invalid or unsupported toolchain lockfile")
    for key, repository in (("oss_cad_suite", "YosysHQ/oss-cad-suite-build"),
                            ("slang", "MikePopoloski/slang")):
        item = lock.get(key)
        if not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise BootstrapError(f"SHA256 pin missing or invalid: {key}")
        if not isinstance(item.get("version"), str) or not re.fullmatch(r"[0-9A-Za-z.-]+", item["version"]):
            raise BootstrapError(f"Unsafe pinned version: {key}")
        if not isinstance(item.get("archive"), str) or not re.fullmatch(r"[0-9A-Za-z._-]+\.(?:tgz|tar\.gz)", item["archive"]):
            raise BootstrapError(f"Unsafe archive filename: {key}")
        url = item.get("url", "")
        expected_url = (f"https://github.com/{repository}/releases/download/"
                        f"{item['version']}/{item['archive']}")
        if url != expected_url:
            raise BootstrapError(f"Untrusted archive URL: {key}")
        if type(item.get("max_bytes")) is not int or item["max_bytes"] < 1024:
            raise BootstrapError(f"Invalid maximum archive bytes: {key}")
    if lock.get("python_extras") != "dev,simulation,mcp" or not isinstance(lock.get("python_versions"), dict):
        raise BootstrapError("Unknown Python project extras")
    return lock


def expected_paths(lock: dict, base: Path = BASE) -> tuple[Path, Path, Path]:
    suite = base / ("oss-cad-suite-" + lock["oss_cad_suite"]["version"])
    slang = base / ("slang-" + lock["slang"]["version"])
    return suite, slang, base / "activate.sh"


def parse_verilator(text: str) -> tuple[int, int] | None:
    match = re.search(r"\bVerilator\s+(\d+)\.(\d+)\b", text)
    return (int(match[1]), int(match[2])) if match else None


def version_tuple(text: str) -> tuple[int, int]:
    result = re.fullmatch(r"(\d+)\.(\d+)", text)
    if not result:
        raise BootstrapError("Invalid Verilator minimum version")
    return (int(result[1]), int(result[2]))


def command_output(cmd: list[str], *, env: dict | None = None) -> str | None:
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=12, check=False, env=env)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def python_versions(venv: Path, pins: dict) -> dict[str, bool]:
    python = venv / "bin" / "python"
    if not python.is_file():
        return {key: False for key in pins}
    code = ("import importlib.metadata as m,json\n"
            "res={}\n"
            "for name in ('cocotb','mcp'):\n"
            " try: res[name]=m.version(name)\n"
            " except m.PackageNotFoundError: res[name]=None\n"
            "print(json.dumps(res))\n")
    output = command_output([str(python), "-c", code])
    if output is None:
        return {key: False for key in pins}
    try:
        values = json.loads(output)
        return {key: values.get(key) == version for key, version in pins.items()}
    except (json.JSONDecodeError, AttributeError):
        return {key: False for key in pins}


def check(lock: dict, *, base: Path = BASE, emit=print) -> bool:
    suite, slang, activation = expected_paths(lock, base)
    expected_verilator = version_tuple(lock["verilator_minimum"])
    paths = {
        "slang": (shutil.which("slang"), lambda out: (
            "slang version " + lock["slang"]["version"].lstrip("v") in out), ["--version"]),
        "verilator": (shutil.which("verilator"), lambda out: (
            (parse_verilator(out) or (0, 0)) >= expected_verilator), ["--version"]),
        "yosys": (shutil.which("yosys"), bool, ["-V"]),
        "sby": (shutil.which("sby"), bool, ["--version"]),
        "eqy": (shutil.which("eqy"), bool, ["--version"]),
        "z3": (shutil.which("z3"), bool, ["--version"]),
        "make": (shutil.which("make"), bool, ["--version"]),
        "g++": (shutil.which("g++"), bool, ["--version"]),
    }
    results = {}
    for name, (path, predicate, args) in paths.items():
        output = command_output([path, *args]) if path else None
        valid = bool(output is not None and predicate(output))
        results[name] = valid
        version = output.splitlines()[0][:110] if output else "not found or failed"
        emit(f"{'OK' if valid else 'MISSING/OLD':11} {name:10} {version} [{path or '-'}]")
    venv = ROOT / ".venv"
    python_ok = python_versions(venv, lock["python_versions"])
    pytest_version = command_output([
        str(venv / "bin" / "python"), "-c",
        "import importlib.metadata as m;print(m.version('pytest'))",
    ]) if (venv / "bin" / "python").is_file() else None
    try:
        python_ok["pytest"] = bool(pytest_version and int(pytest_version.split(".")[0]) >= 7)
    except ValueError:
        python_ok["pytest"] = False
    for name, valid in python_ok.items():
        results["python:" + name] = valid
        expected = lock["python_versions"].get(name, ">=7")
        emit(f"{'OK' if valid else 'MISSING/OLD':11} python:{name:10} expected {expected} in {venv}")
    emit(f"Pinned toolchain directories: suite={suite.is_dir()}, slang={slang.is_dir()}")
    if activation.is_file():
        emit(f"Activation: source {shlex.quote(str(activation))}")
    else:
        emit("Activation script missing; run --install to generate it")
    return all(results.values())


def verify_lock_matches_project(lock: dict) -> None:
    import tomllib
    parsed = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = parsed["project"]["optional-dependencies"]
    for name, version in lock["python_versions"].items():
        if not any(item == f"{name}=={version}" for requirements in extras.values()
                   for item in requirements):
            raise BootstrapError(f"Lock and pyproject disagree on {name}=={version}")


def download_pinned(item: dict, destination: Path) -> None:
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(item["url"], headers={"User-Agent": "RTLPrep-toolchain-bootstrap/1"})
    with urllib.request.urlopen(request, timeout=90) as source, destination.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > item["max_bytes"]:
                raise BootstrapError("Archive exceeds pinned maximum size")
            digest.update(chunk)
            target.write(chunk)
    if digest.hexdigest() != item["sha256"]:
        raise BootstrapError("SHA256 mismatch: refusing to extract unverified archive")


def _archive_parts(name: str) -> tuple[str, ...]:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise BootstrapError(f"Unsafe archive entry: {name!r}")
    clean = path.parts
    if clean[0] in (".", ""):
        clean = clean[1:]
    if not clean:
        raise BootstrapError("Unexpected archive root")
    return clean


def safe_extract(archive: Path, destination: Path) -> None:
    """Extract tar without following external symlinks or trusting file metadata."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if len(members) > MAX_MEMBERS or sum(max(0, x.size) for x in members) > MAX_EXTRACTED_BYTES:
            raise BootstrapError("Archive exceeds extraction safety limits")
        for member in members:
            if member.name in (".", "./") and member.isdir():
                continue
            parts = _archive_parts(member.name)
            if member.issym():
                if posixpath.isabs(member.linkname):
                    raise BootstrapError("Absolute symlink refused")
                resolved = posixpath.normpath(posixpath.join(*parts[:-1], member.linkname))
                if resolved.startswith("../") or resolved in ("..", "."):
                    raise BootstrapError("Symlink escapes destination")
            elif member.islnk():
                linkparts = _archive_parts(member.linkname)
                if ".." in linkparts:
                    raise BootstrapError("Hardlink escapes destination")
            elif not (member.isfile() or member.isdir()):
                raise BootstrapError(f"Unsupported archive entry: {member.name!r}")
        for member in members:
            if member.name in (".", "./") and member.isdir():
                continue
            parts = _archive_parts(member.name)
            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.parent.resolve().is_relative_to(root):
                raise BootstrapError("Archive parent escapes destination")
            if member.isdir():
                target.mkdir(exist_ok=True)
            elif member.issym():
                target.symlink_to(member.linkname)
            else:
                stream = tar.extractfile(member)
                if stream is None:
                    raise BootstrapError("Archive file unavailable")
                # Exclusive creation also refuses duplicate tar entries and symlink writes.
                with stream, target.open("xb") as out:
                    shutil.copyfileobj(stream, out)
                target.chmod(0o755 if (member.mode & 0o111) else 0o644)


def _installed(directory: Path, item: dict, executables: tuple[str, ...]) -> bool:
    marker = directory / ".rtlprep-pinned.json"
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text())
    except (OSError, ValueError):
        return False
    if data.get("version") != item["version"] or data.get("sha256") != item["sha256"]:
        return False
    return all((directory / path).is_file() for path in executables)


def install_archive(item: dict, destination: Path, *, suite: bool,
                    base: Path = BASE) -> bool:
    expected = ("oss-cad-suite/bin/yosys", "oss-cad-suite/bin/verilator",
                "oss-cad-suite/bin/sby", "oss-cad-suite/bin/eqy", "oss-cad-suite/bin/z3") if suite else ("bin/slang",)
    if _installed(destination, item, expected):
        print(f"Already pinned: {destination}")
        return False
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".rtlprep-download-", dir=base) as work:
        directory = Path(work)
        archive = directory / item["archive"]
        stage = directory / "stage"
        print(f"Fetching {item['url']} (SHA256 verified)")
        download_pinned(item, archive)
        safe_extract(archive, stage)
        if not suite:
            matches = [p for p in stage.rglob("slang") if p.is_file() and p.stat().st_mode & stat.S_IXUSR]
            if len(matches) != 1:
                raise BootstrapError("Pinned slang archive has no unique executable")
            (stage / "bin").mkdir(exist_ok=True)
            original = matches[0]
            dest = stage / "bin" / "slang"
            if original != dest:
                shutil.copy2(original, dest)
        if not all((stage / path).is_file() for path in expected):
            raise BootstrapError("Required tools absent from downloaded archive")
        (stage / ".rtlprep-pinned.json").write_text(json.dumps({
            "version": item["version"], "sha256": item["sha256"]
        }), encoding="utf-8")
        old = directory / "previous-install"
        if destination.exists():
            destination.rename(old)
        try:
            stage.rename(destination)
        except OSError:
            if old.exists() and not destination.exists():
                old.rename(destination)
            raise
    print(f"Installed: {destination}")
    return True


def write_activation(base: Path, suite: Path, slang: Path) -> Path:
    activation = base / "activate.sh"
    # shlex.quote protects paths with whitespace / special characters.
    tools = f"{slang / 'bin'}:{suite / 'oss-cad-suite' / 'bin'}"
    text = ("# RTLPrep pinned toolchains: source this file in bash/zsh.\n"
            f"export PATH={shlex.quote(tools)}:\"$PATH\"\n"
            "# Keep the caller's virtual environment Python ahead of CAD Suite Python.\n"
            "if [ -n \"$VIRTUAL_ENV\" ] && [ -d \"$VIRTUAL_ENV/bin\" ]; then\n"
            "  export PATH=\"$VIRTUAL_ENV/bin:$PATH\"\n"
            "fi\n")
    base.mkdir(parents=True, exist_ok=True)
    activation.write_text(text, encoding="utf-8")
    activation.chmod(0o644)
    return activation


def ensure_venv(venv: Path) -> Path:
    python = venv / "bin" / "python"
    if not python.is_file():
        print(f"Creating project virtualenv at {venv}")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    version = command_output([str(python), "-c",
                              "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')"])
    if not version or version_tuple(version) < (3, 11):
        raise BootstrapError("Project .venv must use Python >=3.11; recreate .venv with Python 3.11+")
    return python


def ensure_system_dependencies(*, allow_sudo: bool) -> None:
    missing = [name for name in ("make", "g++") if shutil.which(name) is None]
    if not missing:
        return
    if not allow_sudo:
        raise BootstrapError(
            "Missing system build tools: " + ", ".join(missing) +
            ". On Debian/WSL: sudo apt-get update && sudo apt-get install -y "
            "build-essential; or rerun with --install --with-system"
        )
    if shutil.which("apt-get") is None or shutil.which("sudo") is None:
        raise BootstrapError("--with-system requires sudo and apt-get (Debian/Ubuntu)")
    subprocess.run(["sudo", "apt-get", "update"], check=True)
    subprocess.run(["sudo", "apt-get", "install", "-y", "build-essential"], check=True)
    if any(shutil.which(name) is None for name in missing):
        raise BootstrapError("apt completed but required system build tools are unavailable")


def verify_toolchain(lock: dict, suite: Path, slang: Path) -> None:
    """Verify versions from the installed toolchain, independent of old PATH."""
    suite_bin = suite / "oss-cad-suite" / "bin"
    slang_bin = slang / "bin"
    env = dict(os.environ)
    env["PATH"] = f"{slang_bin}:{suite_bin}:{env.get('PATH', '')}"
    actual_slang = command_output([str(slang_bin / "slang"), "--version"], env=env)
    actual_verilator = command_output([str(suite_bin / "verilator"), "--version"], env=env)
    if not actual_slang or "slang version " + lock["slang"]["version"].lstrip("v") not in actual_slang:
        raise BootstrapError("Downloaded slang failed version check")
    if (parse_verilator(actual_verilator or "") or (0, 0)) < version_tuple(lock["verilator_minimum"]):
        raise BootstrapError("OSS CAD Suite Verilator version is too old for cocotb 2.x")
    for binary, args in (("yosys", ["-V"]), ("sby", ["--version"]),
                         ("eqy", ["--version"]), ("z3", ["--version"])):
        if command_output([str(suite_bin / binary), *args], env=env) is None:
            raise BootstrapError(f"OSS CAD Suite tool cannot start: {binary}")


def install_python(lock: dict, *, update: bool) -> None:
    verify_lock_matches_project(lock)
    python = ensure_venv(ROOT / ".venv")
    argv = [str(python), "-m", "pip", "install"]
    if update:
        argv.append("--upgrade")
    argv += ["-e", f".[{lock['python_extras']}]"]
    print("Installing project Python extras in .venv (versions controlled by pyproject.toml)")
    subprocess.run(argv, cwd=ROOT, check=True)


def update_advice(lock: dict) -> None:
    urls = {
        "oss_cad_suite": "https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/latest",
        "slang": "https://api.github.com/repos/MikePopoloski/slang/releases/latest",
    }
    for name, url in urls.items():
        request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "RTLPrep-toolchain-bootstrap/1"})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                current = json.load(response)["tag_name"]
            print(f"{name}: project pin={lock[name]['version']}, published latest={current}")
        except (OSError, KeyError, ValueError) as exc:
            print(f"{name}: release lookup unavailable ({exc})")
    print("Do not automatically install latest releases. Update pins + SHA256 + CI in a reviewed PR.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument("--check", action="store_true", help="diagnose only (default; no download/writes)")
    choices.add_argument("--install", action="store_true", help="install checked-in toolchains and .venv extras")
    choices.add_argument("--update", action="store_true", help="sync to project pins and upgrade .venv extras")
    choices.add_argument("--check-updates", action="store_true", help="compare latest releases, no changes")
    choices.add_argument("--verify-lock", action="store_true", help="verify lockfile and Python pins, no changes")
    choices.add_argument("--install-rtl-fixtures", action="store_true", help="install pinned external RTL checkouts; never modify existing ones")
    choices.add_argument("--check-rtl-fixtures", action="store_true", help="verify pinned external RTL checkouts offline")
    parser.add_argument("--with-system", action="store_true",
                        help="with --install/--update: authorize sudo apt for missing base packages")
    args = parser.parse_args(argv)
    if args.with_system and not (args.install or args.update):
        parser.error("--with-system requires --install or --update")
    try:
        if args.install_rtl_fixtures or args.check_rtl_fixtures:
            if __package__:
                from .rtl_fixtures import run
            else:
                from rtl_fixtures import run
            return run(ROOT, install=args.install_rtl_fixtures)
        lock = load_lock()
        verify_lock_matches_project(lock)
        if args.verify_lock:
            print("Pinned dependencies match pyproject.toml")
            return 0
        if args.check_updates:
            update_advice(lock)
            return 0
        if args.install or args.update:
            if sys.version_info < (3, 11) or sys.platform != "linux" or platform.machine() not in ("x86_64", "amd64"):
                raise BootstrapError("Installer supports Python >=3.11 on Linux x86_64/WSL only")
            suite, slang, _ = expected_paths(lock)
            # No shell scripts from downloaded tarballs are executed.
            ensure_system_dependencies(allow_sudo=args.with_system)
            install_archive(lock["oss_cad_suite"], suite, suite=True)
            install_archive(lock["slang"], slang, suite=False)
            verify_toolchain(lock, suite, slang)
            script = write_activation(BASE, suite, slang)
            install_python(lock, update=args.update)
            print("\nTo activate in your *current* shell:")
            print(f"  source {shlex.quote(str(ROOT / '.venv' / 'bin' / 'activate'))}")
            print(f"  source {shlex.quote(str(script))}")
            print("  python scripts/rtlprep_env.py --check")
            print("  python -m rtlprep doctor")
            return 0
        ok = check(lock)
        return 0 if ok else 1
    except (BootstrapError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"Dependency setup: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
