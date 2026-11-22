"""Safe, hermetic unit tests for project toolchain bootstrap (no network or sudo)."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rtlprep_env.py"
spec = importlib.util.spec_from_file_location("rtlprep_env", SCRIPT)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def test_checked_in_lock_has_exact_verified_project_versions():
    lock = bootstrap.load_lock()
    bootstrap.verify_lock_matches_project(lock)
    assert lock["oss_cad_suite"]["version"] == "2026-11-18"
    assert lock["slang"]["version"] == "v12.1"
    assert bootstrap.version_tuple(lock["verilator_minimum"]) == (5, 36)
    assert lock["python_versions"] == {"cocotb": "2.0.1", "mcp": "2.3.0"}


def test_lock_rejects_untrusted_url_and_bad_digest(tmp_path):
    data = bootstrap.load_lock()
    data["slang"]["url"] = "http://attack.invalid/bootstrap.sh"
    p = tmp_path / "lock.json"
    p.write_text(json.dumps(data))
    with pytest.raises(bootstrap.BootstrapError, match="Untrusted"):
        bootstrap.load_lock(p)
    data = bootstrap.load_lock()
    data["oss_cad_suite"]["sha256"] = "wrong"
    p.write_text(json.dumps(data))
    with pytest.raises(bootstrap.BootstrapError, match="SHA256"):
        bootstrap.load_lock(p)


def _tgz(path: Path, entries):
    with tarfile.open(path, "w:gz") as tar:
        for name, contents, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                b = contents.encode()
                info.size = len(b)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(b))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = contents
                tar.addfile(info)
            elif kind == "directory":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
    return path


def test_extract_rejects_absolute_path_and_traversal(tmp_path):
    for name in ("/tmp/pwned", "../pwned", "ok/../../pwned"):
        archive = _tgz(tmp_path / "archive.tgz", [(name, "bad", "file")])
        with pytest.raises(bootstrap.BootstrapError, match="Unsafe"):
            bootstrap.safe_extract(archive, tmp_path / "dest")


def test_extract_rejects_symlink_escapes(tmp_path):
    for link in ("../../../outside", "/etc/passwd"):
        archive = _tgz(tmp_path / "archive.tgz", [
            ("bin/bin-link", link, "symlink")
        ])
        with pytest.raises(bootstrap.BootstrapError, match="(Symlink|Absolute)"):
            bootstrap.safe_extract(archive, tmp_path / "dest")


def test_extract_allows_internal_symlink_without_following_outside(tmp_path):
    archive = _tgz(tmp_path / "archive.tgz", [
        ("./", "", "directory"), ("oss-cad-suite/bin/yosys", "binary", "file"),
        ("oss-cad-suite/bin/yosys-link", "yosys", "symlink"),
    ])
    out = tmp_path / "dest"
    bootstrap.safe_extract(archive, out)
    assert (out / "oss-cad-suite/bin/yosys").read_text() == "binary"
    assert (out / "oss-cad-suite/bin/yosys-link").is_symlink()


def test_bad_checksum_does_not_create_trusted_install(tmp_path, monkeypatch):
    archive = _tgz(tmp_path / "remote.tgz", [("bin/slang", "binary", "file")])
    class Response:
        def __enter__(self):
            return archive.open("rb")
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", lambda *a, **kw: Response())
    item = bootstrap.load_lock()["slang"].copy()
    item["sha256"] = "0" * 64
    with pytest.raises(bootstrap.BootstrapError, match="SHA256 mismatch"):
        bootstrap.download_pinned(item, tmp_path / "download.tgz")


def test_pinned_install_is_idempotent_without_network(tmp_path, monkeypatch):
    archive = _tgz(tmp_path / "cached.tgz", [("bin/slang", "binary", "file")])
    item = bootstrap.load_lock()["slang"].copy()
    item["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    def mock_download(_, destination):
        destination.write_bytes(archive.read_bytes())
    monkeypatch.setattr(bootstrap, "download_pinned", mock_download)
    base = tmp_path / "toolchains"
    installed = base / "slang-v12.1"
    assert bootstrap.install_archive(item, installed, suite=False, base=base)
    assert (installed / "bin/slang").read_text() == "binary"
    monkeypatch.setattr(bootstrap, "download_pinned", lambda *_: pytest.fail("unexpected download"))
    assert bootstrap.install_archive(item, installed, suite=False, base=base) is False


def test_activation_keeps_virtualenv_python_first(tmp_path):
    base = tmp_path / "tools with space"
    suite = base / "suite"
    slang = base / "slang"
    script = bootstrap.write_activation(base, suite, slang)
    code = script.read_text()
    assert "VIRTUAL_ENV/bin:$PATH" in code
    assert "oss-cad-suite/bin" in code
    assert "slang/bin" in code
    assert script.stat().st_mode & 0o111 == 0


def test_version_parser_does_not_accept_old_verilator():
    assert bootstrap.parse_verilator("Verilator 5.008 2022-01-01") == (5, 8)
    assert bootstrap.parse_verilator("Verilator 5.040 2025-01-01") == (5, 40)
    assert bootstrap.parse_verilator("something else") is None


def test_missing_system_tools_does_not_sudo_by_default(monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda _x: None)
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *a, **kw: pytest.fail("sudo called"))
    with pytest.raises(bootstrap.BootstrapError, match="build-essential"):
        bootstrap.ensure_system_dependencies(allow_sudo=False)


def test_check_has_no_network_or_mutation(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda _: None)
    monkeypatch.setattr(bootstrap, "python_versions", lambda *_: {"cocotb": False, "mcp": False})
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", lambda *_: pytest.fail("network"))
    result = []
    assert bootstrap.check(bootstrap.load_lock(), base=tmp_path, emit=result.append) is False
    assert not list(tmp_path.iterdir())
    assert any("verilator" in x for x in result)
    assert any("cocotb" in x for x in result)
