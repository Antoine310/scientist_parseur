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


def test_real_slang_csr_operator_difference_is_visible_in_expressions(tmp_path):
    """Vérifie que slang distingue OU/ET même avec un graphe de liens identique."""
    import json
    from rtlprep.runner import dependency_design

    trees = []
    edges = []
    for name in ("design.json", "buggy_design.json"):
        d = load_design(ROOT / "examples/security_csr" / name)
        out = tmp_path / name
        result = dependency_design(d, out, timeout=90)
        assert result["status"] == "passed", result
        graph = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
        entries = [item for item in graph["expressions"]["items"]
                   if item["target"] == "secure_csr.write_accepted_o"]
        assert len(entries) == 1, graph["expressions"]["counts"]
        assert entries[0]["coverage"] == "syntax_supported", entries[0]
        trees.append(entries[0]["expression"])
        edges.append({(edge["source"], edge["target"], edge["kind"])
                      for edge in graph["edges"]})
    assert edges[0] == edges[1]
    assert trees[0] != trees[1]
    # Only the buggy CSR has a LogicalOr operator; both use LogicalAnd.
    def operators(tree):
        if not isinstance(tree, dict):
            return set()
        result = {tree["operator"]} if "operator" in tree else set()
        for key in ("left", "right", "operand"):
            result.update(operators(tree.get(key)))
        return result
    assert "LogicalOr" not in operators(trees[0]), trees[0]
    assert "LogicalOr" in operators(trees[1]), trees[1]
    assert "LogicalAnd" in operators(trees[0]) & operators(trees[1])


def test_real_slang_counter_if_else_and_event_provenance(tmp_path):
    """Vrai AST slang : reset et incrément non bloquants sous gardes distinctes."""
    import json
    from rtlprep.runner import dependency_design

    design = load_design(ROOT / "examples/counter/design.json")
    result = dependency_design(design, tmp_path / "counter", timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    data = graph["expressions"]
    rows = [item for item in data["items"] if item["target"] == "counter.count"]
    assert len(rows) == 2, data["counts"]
    assert all(row["assignment_kind"] == "procedural" for row in rows)
    assert all(row["procedure_kind"] == "AlwaysFF" for row in rows)
    assert all(row["nonblocking"] is True for row in rows)
    assert all(row["coverage"] == "syntax_supported" for row in rows), rows
    assert all(row["source"] and row["source"]["file"].endswith("counter.sv")
               and row["source"]["line"] >= 8 for row in rows), rows
    for row in rows:
        assert {(event["edge"], event["expression"].get("path"))
                for event in row["events"]} == {
                    ("PosEdge", "counter.clk"),
                    ("NegEdge", "counter.rst_n"),
                }, row
    reset, increment = sorted(rows, key=lambda row: len(row["guards"]))
    assert [g["branch"] for g in reset["guards"]] == ["then"]
    assert reset["guards"][0]["expression"]["operator"] == "LogicalNot"
    assert reset["guards"][0]["expression"]["operand"]["path"] == "counter.rst_n"
    assert [g["branch"] for g in increment["guards"]] == ["else", "then"]
    assert increment["guards"][1]["expression"]["path"] == "counter.enable"
    assert increment["expression"]["operator"] == "Add"


def test_real_slang_csr_write_guard_in_always_ff(tmp_path):
    """La condition write_accepted_o apparaît dans le chemin de mise à jour."""
    import json
    from rtlprep.runner import dependency_design

    design = load_design(ROOT / "examples/security_csr/design.json")
    result = dependency_design(design, tmp_path / "csr", timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    rows = [item for item in graph["expressions"]["items"]
            if item["target"] == "secure_csr.value_o"]
    assert len(rows) == 2, rows
    updates = [row for row in rows if len(row["guards"]) == 2]
    assert len(updates) == 1, rows
    update = updates[0]
    assert [g["branch"] for g in update["guards"]] == ["else", "then"]
    assert update["guards"][1]["expression"]["path"] == (
        "secure_csr.write_accepted_o"
    )
    assert update["nonblocking"] is True
    assert update["expression"]["path"] == "secure_csr.wdata_i"
    assert update["coverage"] == "syntax_supported", update


def test_real_slang_advanced_case_selection_context(tmp_path):
    """Normal case : garder sélecteur et étiquettes, sans synthétiser un prédicat."""
    import json
    from rtlprep.runner import dependency_design

    design = load_design(ROOT / "examples/advanced/design.json")
    result = dependency_design(design, tmp_path / "advanced", timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    rows = [item for item in graph["expressions"]["items"]
            if item["target"] == "advanced_logic.result"
            and item.get("assignment_kind") == "procedural"]
    assert len(rows) >= 2, graph["expressions"]["counts"]
    assert all(any(guard["kind"] == "case" for guard in item["guards"])
               for item in rows), rows
    assert all(any(guard["selector"].get("path") == "advanced_logic.sel"
                   for guard in item["guards"] if guard["kind"] == "case")
               for item in rows), rows


def test_real_slang_register_flow_counter_candidates_and_guard_order(tmp_path):
    """Trois chemins AST : reset, incrément et absence syntaxique d'écriture."""
    import json
    from rtlprep.runner import dependency_design

    design = load_design(ROOT / "examples/counter/design.json")
    result = dependency_design(design, tmp_path / "register-paths", timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    records = graph["register_flow"]["items"]
    matched = [r for r in records if r["target"] == "counter.count"]
    assert len(matched) == 1, graph["register_flow"]["counts"]
    row = matched[0]
    assert row["coverage"] == "syntactic_paths_supported", row
    assert row["path_count"] == 3, row
    assert row["hold_candidate"] == "syntactic_unwritten_path", row
    assert row["same_path_multiple_nba"] is False
    assert {(e["edge"], e["signal"]) for e in row["events"]} == {
        ("PosEdge", "counter.clk"), ("NegEdge", "counter.rst_n")
    }
    assert sorted(p["write_count"] for p in row["paths"]) == [0, 1, 1]
    assert any([g["branch"] for g in p["guards"]] == ["else", "else"]
               and p["last_nonblocking_write"] is None
               for p in row["paths"])
    assert {p["last_nonblocking_write"]["source"]["line"] for p in row["paths"]
            if p["last_nonblocking_write"]} == {9, 11}


def test_real_slang_register_flow_csr_hold_candidate(tmp_path):
    """Le contrôle write_accepted_o laisse un chemin sans écriture dans FF."""
    import json
    from rtlprep.runner import dependency_design

    design = load_design(ROOT / "examples/security_csr/design.json")
    result = dependency_design(design, tmp_path / "csr-register-paths", timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    rows = [r for r in graph["register_flow"]["items"]
            if r["target"] == "secure_csr.value_o"]
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["coverage"] == "syntactic_paths_supported", row
    assert row["hold_candidate"] == "syntactic_unwritten_path"
    assert row["path_count"] == 3
    assert any(p["guards"][-1]["condition"].get("path") ==
               "secure_csr.write_accepted_o" for p in row["paths"]
               if p["guards"][-1]["branch"] == "then"), row


def test_real_slang_static_bit_accesses_in_advanced_example(tmp_path):
    """Vrai slang : concaténation de deux tranches et index dynamique."""
    import json
    from rtlprep.runner import dependency_design

    design = load_design(ROOT / "examples/advanced/design.json")
    result = dependency_design(design, tmp_path / "bit-lanes", timeout=90)
    assert result["status"] == "passed", result
    graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
    data = graph["bit_accesses"]
    merged = [x for x in data["items"] if x["target"] == "advanced_logic.merged"]
    picked = [x for x in data["items"] if x["target"] == "advanced_logic.picked"]
    assert len(merged) == 1, data["counts"]
    assert merged[0]["coverage"] == "rhs_lanes_only", merged[0]
    assert merged[0]["rhs_width"] == 8, merged[0]
    assert [(x["source"], x["rhs_lsb"], x["rhs_msb"]) for x in merged[0]["source_segments"]] == [
        ("advanced_logic.data_a", 4, 7),
        ("advanced_logic.data_b", 0, 3),
    ]
    assert len(picked) == 1, data["counts"]
    assert picked[0]["coverage"] == "partial", picked[0]
    assert picked[0]["reason"] == "dynamic_or_unknown_index", picked[0]


def test_real_slang_coverage_counter_and_advanced(tmp_path):
    """Une synthèse des éléments observés, pas un taux de RTL couvert."""
    import json
    from rtlprep.runner import dependency_design

    for example in ("counter", "advanced"):
        design = load_design(ROOT / "examples" / example / "design.json")
        result = dependency_design(design, tmp_path / example, timeout=90)
        assert result["status"] == "passed", result
        graph = json.loads(Path(result["dependencies"]).read_text(encoding="utf-8"))
        coverage = graph["coverage"]
        assert coverage["scope"] == "observed_analyzer_records_only", coverage
        assert coverage["design_coverage"] == "not_measured", coverage
        assert coverage["analyzers"]["dependencies"]["edges"] == len(graph["edges"])
        assert coverage["analyzers"]["expressions"]["captured"] == len(
            graph["expressions"]["items"]
        )
        assert coverage["analyzers"]["register_flow"]["captured"] == len(
            graph["register_flow"]["items"]
        )
        assert coverage["analyzers"]["bit_accesses"]["captured"] == len(
            graph["bit_accesses"]["items"]
        )
        assert coverage["findings_total"] >= len(coverage["findings"])
        if example == "counter":
            assert coverage["analyzers"]["register_flow"]["observed_status_counts"][
                "syntactic_paths_supported"
            ] >= 1
        else:
            assert coverage["analyzers"]["bit_accesses"]["observed_status_counts"][
                "partial"
            ] >= 1
            assert any("dynamic_or_unknown_index" == f["reason"] for f in coverage["findings"])
