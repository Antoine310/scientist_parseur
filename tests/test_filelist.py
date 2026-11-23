"""Importeur de filelists : sûreté, fidélité des sources et génération de manifestes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rtlprep.filelist import FilelistError, parse_filelist, write_manifest
from rtlprep.manifest import load_design
from rtlprep.runner import common_slang_args

ROOT = Path(__file__).resolve().parents[1]


def project(tmp_path):
    base = tmp_path / "chip"
    (base / "rtl" / "include").mkdir(parents=True)
    (base / "lists").mkdir()
    (base / "rtl" / "pkg.sv").write_text("package pkg; endpackage\n")
    (base / "rtl" / "top.sv").write_text("module chip_top; endmodule\n")
    (base / "rtl" / "include" / "defs.svh").write_text("// header\n")
    (base / "lists" / "packages.f").write_text("../rtl/pkg.sv\n")
    root = base / "compile.f"
    root.write_text(
        "# comment\n"
        "+incdir+rtl/include // inline comment\n"
        "+define+IMPORT_ON+MODE=1\n"
        "-f lists/packages.f\n"
        "rtl/top.sv\n"
        "rtl/top.sv # repeated\n"
    )
    return base, root


def test_nested_filelist_preserves_order_and_manifest_is_consumable(tmp_path):
    base, entry = project(tmp_path)
    target = tmp_path / "reports" / "design.json"
    result = write_manifest(entry, root=base, top="chip_top", output=target)
    assert result["sources_count"] == 2
    assert result["include_dirs_count"] == 1
    assert result["defines_count"] == 2
    assert result["filelists_count"] == 2
    d = load_design(target)
    assert [p.name for p in d.sources] == ["pkg.sv", "top.sv"]
    assert d.includes == ((base / "rtl/include").resolve(),)
    assert d.defines == ("IMPORT_ON", "MODE=1")
    assert ["-I" + str(d.includes[0])] == [
        x for x in common_slang_args(d) if x.startswith("-I")
    ]
    saved = json.loads(target.read_text())
    assert saved["filelist_import"]["scope"].startswith("explicit_filelist_entries")
    assert len(saved["filelist_import"]["filelists"][0]["sha256"]) == 64


def test_f_and_F_inline_quote_and_continuations(tmp_path):
    base, entry = project(tmp_path)
    src = base / "rtl" / "another module.sv"
    src.write_text("module another; endmodule\n")
    entry.write_text(
        '-Irtl/include -DMODE=2 \\\n'
        '-Flists/packages.f\n'
        '"rtl/another module.sv"\n'
        'rtl/top.sv\n'
    )
    parsed = parse_filelist(entry, root=base, top="chip_top")
    assert [p.name for p in parsed["_resolved_sources"]] == [
        "pkg.sv", "another module.sv", "top.sv"
    ]
    assert parsed["_defines"] == ["MODE=2"]


def test_duplicate_nested_filelists_are_allowed_but_sources_deduplicated(tmp_path):
    base, entry = project(tmp_path)
    entry.write_text("-f lists/packages.f\n-F lists/packages.f\nrtl/top.sv\n")
    parsed = parse_filelist(entry, root=base, top="chip_top")
    assert len(parsed["_resolved_sources"]) == 2
    assert len(parsed["_import"]["filelists"]) == 3


def test_refuse_cycles(tmp_path):
    base, entry = project(tmp_path)
    (base / "lists/packages.f").write_text("-f ../compile.f\n")
    with pytest.raises(FilelistError, match="Boucle"):
        parse_filelist(entry, root=base, top="chip_top")


@pytest.mark.parametrize("token", [
    "-y rtl", "-v rtl/top.sv", "-timescale 1ns/1ps",
    "+libext+.sv", "@response", "+not_supported",
    "rtl/*.sv", "rtl/$PROJECT/top.sv",
    "rtl/" + "$" + "{ROOT}/top.sv", "rtl/../outside/top.sv",
    "http://malicious.example/top.sv", "rtl/top.svh",
    "+define+BAD=hello.world\nrtl/top.sv",
    "-D 'BAD=very long value'\nrtl/top.sv",
])
def test_fail_closed_for_unsupported_or_ambiguous_options(tmp_path, token):
    base, entry = project(tmp_path)
    entry.write_text(f"{token}\nrtl/top.sv\n")
    with pytest.raises((FilelistError, ValueError)):
        parse_filelist(entry, root=base, top="chip_top")


def test_reject_filelist_outside_root(tmp_path):
    base, entry = project(tmp_path)
    outside = tmp_path / "outside.f"
    outside.write_text("rtl/top.sv\n")
    with pytest.raises(FilelistError, match="sort de --root"):
        parse_filelist(outside, root=base, top="chip_top")


def test_reject_source_symlink_escape(tmp_path):
    base, entry = project(tmp_path)
    outside = tmp_path / "secret.sv"
    outside.write_text("module secret; endmodule\n")
    (base / "rtl" / "outside.sv").symlink_to(outside)
    entry.write_text("rtl/outside.sv\n")
    with pytest.raises(FilelistError, match="sort de --root"):
        parse_filelist(entry, root=base, top="chip_top")


def test_reject_include_dir_symlink_escape(tmp_path):
    base, entry = project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (base / "bad_link").symlink_to(outside, target_is_directory=True)
    entry.write_text("+incdir+bad_link\nrtl/top.sv\n")
    with pytest.raises(FilelistError, match="sort de --root"):
        parse_filelist(entry, root=base, top="chip_top")


@pytest.mark.parametrize("top", ["bad.top", "../bad", "not valid", "", "-o"])
def test_top_must_be_simple_identifier(tmp_path, top):
    base, entry = project(tmp_path)
    with pytest.raises(FilelistError, match="Top"):
        parse_filelist(entry, root=base, top=top)


def test_failed_import_never_creates_output(tmp_path):
    base, entry = project(tmp_path)
    entry.write_text("-y libs\nrtl/top.sv\n")
    output = tmp_path / "reports/design.json"
    with pytest.raises(FilelistError):
        write_manifest(entry, root=base, top="chip_top", output=output)
    assert not output.exists()


def test_overwrite_requires_explicit_force_and_preserves_input(tmp_path):
    base, entry = project(tmp_path)
    output = tmp_path / "design.json"
    write_manifest(entry, root=base, top="chip_top", output=output)
    with pytest.raises(FilelistError, match="--force"):
        write_manifest(entry, root=base, top="chip_top", output=output)
    write_manifest(entry, root=base, top="chip_top", output=output, overwrite=True)
    assert json.loads(output.read_text())["top"] == "chip_top"
    with pytest.raises(FilelistError, match="ne peut remplacer"):
        write_manifest(entry, root=base, top="chip_top", output=entry, overwrite=True)
    with pytest.raises(FilelistError, match="ne peut remplacer"):
        write_manifest(entry, root=base, top="chip_top",
                       output=base / "rtl/top.sv", overwrite=True)


def test_list_byte_limits_apply_before_read(tmp_path, monkeypatch):
    base, entry = project(tmp_path)
    import rtlprep.filelist as tool
    monkeypatch.setattr(tool, "MAX_FILE_BYTES", 8)
    with pytest.raises(FilelistError, match="volumineuse"):
        parse_filelist(entry, root=base, top="chip_top")


def test_empty_source_list_rejected(tmp_path):
    base, entry = project(tmp_path)
    entry.write_text("# empty\n+incdir+rtl/include\n")
    with pytest.raises(FilelistError, match="Aucune source"):
        parse_filelist(entry, root=base, top="chip_top")


def test_cli_real_without_eda_and_readable_with_existing_loader(tmp_path):
    base, entry = project(tmp_path)
    output = tmp_path / "reports" / "design.json"
    call = [
        sys.executable, "-m", "rtlprep", "import-filelist", str(entry),
        "--root", str(base), "--top", "chip_top", "--out", str(output),
    ]
    result = subprocess.run(call, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["sources_count"] == 2
    assert load_design(output).top == "chip_top"
    again = subprocess.run(call, capture_output=True, text=True, cwd=ROOT)
    assert again.returncode == 2
    assert "ajouter --force" in again.stderr
