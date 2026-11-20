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


def test_real_slang_dependency_graph(tmp_path):
    """Contrôle sémantique des vrais nœuds slang : data/control/event/ports."""
    import json
    from rtlprep.runner import dependency_design
    from rtlprep.dependencies import trace_dependencies

    d = load_design(ROOT / "examples/dependencies/design.json")
    result = dependency_design(d, tmp_path, timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    expected = {
        ("dependency_top.a", "dependency_top.child.a", "port_input"),
        ("dependency_top.b", "dependency_top.child.b", "port_input"),
        ("dependency_top.sel", "dependency_top.child.sel", "port_input"),
        ("dependency_top.child.a", "dependency_top.child.and_result", "data"),
        ("dependency_top.child.b", "dependency_top.child.and_result", "data"),
        ("dependency_top.child.and_result", "dependency_top.child.y", "data"),
        ("dependency_top.child.sel", "dependency_top.child.y", "control"),
        ("dependency_top.child.y", "dependency_top.interm", "port_output"),
        ("dependency_top.interm", "dependency_top.out", "data"),
        ("dependency_top.enable", "dependency_top.count", "control"),
        ("dependency_top.rst_n", "dependency_top.count", "control"),
        ("dependency_top.clk", "dependency_top.count", "event"),
        ("dependency_top.rst_n", "dependency_top.count", "event"),
        ("dependency_top.count", "dependency_top.count", "data"),
    }
    assert expected.issubset(edges), sorted(expected - edges)
    assert graph["counts"]["warnings"] == 0, graph["warnings"]
    assert "dependency_top.a" in trace_dependencies(
        graph, "dependency_top.out", "fanin", max_depth=6
    )["visited_nodes"]


def test_real_slang_case_concat_bit_select_and_generate(tmp_path):
    """Toutes les dépendances attendues viennent du compilateur slang réel."""
    import json
    from rtlprep.runner import dependency_design
    from rtlprep.dependencies import trace_dependencies

    d = load_design(ROOT / "examples/advanced/design.json")
    result = dependency_design(d, tmp_path, timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    expected = {
        ("advanced_logic.data_a", "advanced_logic.merged", "data"),
        ("advanced_logic.data_b", "advanced_logic.merged", "data"),
        ("advanced_logic.data_a", "advanced_logic.picked", "data"),
        ("advanced_logic.idx", "advanced_logic.picked", "data"),
        ("advanced_logic.sel", "advanced_logic.result", "control"),
        ("advanced_logic.merged", "advanced_logic.result", "data"),
        ("advanced_logic.data_a", "advanced_logic.result", "data"),
        ("advanced_logic.data_b", "advanced_logic.result", "data"),
        ("advanced_logic.data_a", "advanced_logic.mode_result", "data"),
        ("advanced_logic.data_b", "advanced_logic.mode_result", "data"),
    }
    assert expected.issubset(edges), sorted(expected - edges)
    assert graph["counts"]["warnings"] == 1, graph["warnings"]
    assert "Sélection de bits/plage" in graph["warnings"][0]["reason"]
    assert "advanced_logic.data_a" in trace_dependencies(
        graph, "advanced_logic.result", "fanin", max_depth=3
    )["visited_nodes"]


def test_real_slang_alternative_generate_branch(tmp_path):
    """Avec USE_XOR=0, slang doit élaborer la branche OR et non XOR."""
    import json
    from rtlprep.runner import dependency_design

    d = load_design(ROOT / "examples/advanced/alternative_design.json")
    result = dependency_design(d, tmp_path, timeout=90)
    assert result["status"] == "passed", result
    ast = json.loads((tmp_path / "elaborated_ast.json").read_text(encoding="utf-8"))
    root = next(x for x in ast["design"]["members"] if x.get("kind") == "Instance")
    child = next(x for x in root["body"]["members"]
                 if x.get("kind") == "Instance" and x.get("name") == "dut")
    blocks = [x for x in child["body"]["members"] if x.get("kind") == "GenerateBlock"]
    active = [x for x in blocks if x.get("isUninstantiated") is not True]
    assert len(active) == 1, blocks
    assigns = [x["assignment"] for x in active[0]["members"]
               if x.get("kind") == "ContinuousAssign"]
    assert len(assigns) == 1
    assert assigns[0]["right"]["kind"] == "BinaryOp"
    assert assigns[0]["right"]["op"] == "BinaryOr"

    graph = json.loads((tmp_path / "rtl_dependencies.json").read_text(encoding="utf-8"))
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    assert ("alternative_top.dut.data_a",
            "alternative_top.dut.mode_result", "data") in edges
    assert ("alternative_top.dut.data_b",
            "alternative_top.dut.mode_result", "data") in edges
