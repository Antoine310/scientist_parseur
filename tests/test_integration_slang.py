"""Tests d'intégration réels : sautés si l'exécutable slang n'est pas installé."""
import shutil
from pathlib import Path

import pytest

from rtlprep.manifest import load_design
from rtlprep.runner import analyze

pytestmark = pytest.mark.skipif(shutil.which("slang") is None, reason="slang non installé")
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("example,top,expected_paths", [
    ("counter", "counter", {"counter"}),
    ("hierarchy", "hierarchy_top", {
        "hierarchy_top", "hierarchy_top.first", "hierarchy_top.second"
    }),
])
def test_real_slang_ast(tmp_path, example, top, expected_paths):
    import json

    d = load_design(ROOT / "examples" / example / "design.json")
    result = analyze(d, tmp_path / example, timeout=90)
    assert result["status"] == "passed", result
    summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
    assert summary["top"] == top
    assert expected_paths.issubset({i["hierarchy_path"] for i in summary["instances"]})
    assert summary["instance_count"] == len(expected_paths)
    by_path = {entry["hierarchy_path"]: entry for entry in summary["instances"]}
    assert len(by_path) == len(expected_paths)
    assert by_path[top]["module"] == top
    if example == "counter":
        ports = {port["name"]: port["direction"] for port in by_path[top]["ports"]}
        assert ports == {"clk": "In", "rst_n": "In", "enable": "In", "count": "Out"}
    else:
        for instance in ("first", "second"):
            leaf = by_path[f"hierarchy_top.{instance}"]
            assert leaf["module"] == "leaf"
            assert {p["name"]: p["direction"] for p in leaf["ports"]} == {
                "enable": "In", "status": "Out"
            }


def test_real_slang_structured_index(tmp_path):
    import json
    from rtlprep.runner import index_design
    from rtlprep.index import get_signal_info, get_module_summary

    d = load_design(ROOT / "examples/hierarchy/design.json")
    result = index_design(d, tmp_path, timeout=90)
    assert result["status"] == "passed", result
    idx = json.loads(Path(result["index"]).read_text(encoding="utf-8"))
    assert idx["schema_version"] == 1
    assert idx["counts"]["modules"] == 2
    assert idx["counts"]["instances"] == 3
    assert [x["path"] for x in idx["instances"]] == [
        "hierarchy_top", "hierarchy_top.first", "hierarchy_top.second"
    ]
    assert get_module_summary(idx, "leaf")["instance_paths"] == [
        "hierarchy_top.first", "hierarchy_top.second"
    ]
    for name in ("first", "second"):
        path = f"hierarchy_top.{name}"
        info = get_signal_info(idx, path, "status")
        assert info["ports"][0]["direction"] == "Out"
        assert info["declarations"][0]["kind"] == "Variable"
        # Vérifie la provenance provenant de slang, pas d'une regex.
        assert info["ports"][0]["source"]["file"].endswith("leaf.sv")
        assert info["ports"][0]["source"]["line"] >= 1
    assert idx["instances"][0]["source"]["file"].endswith("top.sv")
