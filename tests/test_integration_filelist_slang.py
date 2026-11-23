"""Compile real packages + includes + defines after safe filelist import."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.filelist import write_manifest
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "filelist_project"


@pytest.mark.skipif(shutil.which("slang") is None, reason="slang requis pour AST reel")
def test_real_slang_compiles_imported_project(tmp_path):
    manifest = tmp_path / "imported" / "design.json"
    report = write_manifest(PROJECT / "compile.f", root=PROJECT,
                            top="imported_top", output=manifest)
    assert report["sources_count"] == 2
    assert report["include_dirs_count"] == 1
    assert report["filelists_count"] == 2
    assert report["defines_count"] == 1
    design = load_design(manifest)
    assert [p.name for p in design.sources] == ["pkg.sv", "top.sv"]
    out = tmp_path / "analysis"
    result = dependency_design(design, out, timeout=90)
    assert result["status"] == "passed", result
    index = json.loads((out / "rtl_index.json").read_text())
    graph = json.loads((out / "rtl_dependencies.json").read_text())
    assert index["top"] == graph["top"] == "imported_top"
    assert graph["counts"]["edges"] > 0, graph["counts"]
    assert index["source_fingerprint"] == graph["source_fingerprint"]
    assert (out / "deps.result.json").exists()
