"""Syntax trees extracted from AST, without parsing source RTL or running EDA."""
from __future__ import annotations

import json

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.mcp_data import ReadOnlyRtl


def _ref(name: str) -> dict:
    return {"kind": "NamedValue", "symbol": "123456 " + name}


def _binary(op: str, left: dict, right: dict) -> dict:
    return {"kind": "BinaryOp", "op": op, "left": left, "right": right}


def _ast(inner_operator: str) -> dict:
    signals = ["write_i", "machine_mode_i", "debug_locked_i", "grant"]
    members = [
        {"kind": "Port", "name": name, "direction": "Out" if name == "grant" else "In"}
        for name in signals
    ]
    members.extend(
        {"kind": "Variable", "name": name, "type": "logic"}
        for name in signals
    )
    members.append({
        "kind": "ContinuousAssign",
        "assignment": {
            "kind": "Assignment",
            "left": _ref("grant"),
            "right": _binary("LogicalAnd", _ref("write_i"),
                             _binary(inner_operator, _ref("machine_mode_i"),
                                     {"kind": "UnaryOp", "op": "LogicalNot",
                                      "operand": _ref("debug_locked_i")})),
            "source_file_start": "fixture.sv",
            "source_line_start": 12,
        },
    })
    return {
        "design": {"kind": "Root", "members": [{
            "kind": "Instance", "name": "unit",
            "body": {"kind": "InstanceBody", "name": "unit", "members": members},
        }]},
    }


def test_same_dependency_edges_but_different_expression_operators():
    good = build_dependency_graph(_ast("LogicalAnd"), expected_top="unit")
    bad = build_dependency_graph(_ast("LogicalOr"), expected_top="unit")
    assert good["edges"] == bad["edges"]  # Original graph cannot distinguish.
    for graph, inner in ((good, "LogicalAnd"), (bad, "LogicalOr")):
        data = graph["expressions"]
        assert data["schema_version"] == 1
        assert data["counts"]["captured"] == 1
        row = data["items"][0]
        assert row["target"] == "unit.grant"
        assert row["source"] == {"file": "fixture.sv", "line": 12}
        assert row["coverage"] == "syntax_supported"
        assert row["expression"]["operator"] == "LogicalAnd"
        assert row["expression"]["right"]["operator"] == inner
        assert row["expression"]["right"]["right"]["operator"] == "LogicalNot"
        assert row["expression"]["left"] == {
            "kind": "signal", "name": "write_i", "path": "unit.write_i",
        }


def test_unknown_rhs_fails_explicitly_without_fabricating_expression():
    ast = _ast("LogicalAnd")
    assignment = ast["design"]["members"][0]["body"]["members"][-1]["assignment"]
    assignment["right"]["right"] = {"kind": "Call", "args": [123]}
    idx = build_dependency_graph(ast, expected_top="unit")["expressions"]
    assert idx["counts"]["partial_expressions"] == 1
    assert idx["items"][0]["coverage"] == "partial"
    assert idx["items"][0]["expression"]["right"]["kind"] == "unsupported"


def test_procedural_assignments_are_captured_without_inventing_timing():
    ast = _ast("LogicalAnd")
    members = ast["design"]["members"][0]["body"]["members"]
    members.append({"kind": "ProceduralBlock", "procedureKind": "AlwaysComb",
                    "body": {"kind": "ExpressionStatement",
                             "expr": {"kind": "Assignment", "left": _ref("grant"),
                                      "right": _ref("write_i"),
                                      "isNonBlocking": False}}})
    data = build_dependency_graph(ast, expected_top="unit")["expressions"]
    assert data["counts"]["captured"] == 2
    assert data["counts"]["procedural_blocks_visited"] == 1
    assert data["counts"]["procedural_blocks_skipped"] == 0
    assert data["scope"] == "continuous_and_supported_procedural_assignments"
    row = next(item for item in data["items"]
               if item.get("assignment_kind") == "procedural")
    assert row["procedure_kind"] == "AlwaysComb"
    assert row["events"] == []  # No explicit clock edge implied.
    assert row["nonblocking"] is False
    assert row["coverage"] == "syntax_supported"


def test_mcp_reads_only_saved_bounded_expressions(tmp_path):
    graph = build_dependency_graph(_ast("LogicalOr"), expected_top="unit")
    graph["source_fingerprint"] = "snapshot_a"
    path = tmp_path / "rtl_dependencies.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    api = ReadOnlyRtl(graph_file=path)
    assert api.capabilities()["expressions_available"] is True
    result = api.expressions("unit.grant", limit=1)
    assert result["total"] == 1
    assert result["items"][0]["expression"]["right"]["operator"] == "LogicalOr"
    assert result["source_snapshot_status"] == "unverifiable"
    assert api.expressions("unit.write_i")["total"] == 0
    with pytest.raises(KeyError):
        api.expressions("unit.unknown")
    for limit, offset in ((0, 0), (101, 0), (1, -1)):
        with pytest.raises(ValueError):
            api.expressions("unit.grant", limit=limit, offset=offset)
    with pytest.raises(KeyError):
        api.expressions("../etc/passwd")


def test_old_graph_does_not_pretend_expressions_are_empty(tmp_path):
    graph = build_dependency_graph(_ast("LogicalAnd"), expected_top="unit")
    del graph["expressions"]
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(graph), encoding="utf-8")
    api = ReadOnlyRtl(graph_file=p)
    assert api.capabilities()["expressions_available"] is False
    with pytest.raises(ValueError, match="régénérer"):
        api.expressions("unit.grant")


def _assign_procedural(rhs, *, nb=True):
    return {"kind": "ExpressionStatement", "expr": {
        "kind": "Assignment", "left": _ref("grant"), "right": rhs,
        "isNonBlocking": nb,
    }}


def test_nested_if_else_and_always_ff_events_are_preserved():
    ast = _ast("LogicalAnd")
    members = ast["design"]["members"][0]["body"]["members"]
    members.append({
        "kind": "ProceduralBlock", "procedureKind": "AlwaysFF",
        "body": {
            "kind": "Timed",
            "timing": {"kind": "EventList", "events": [
                {"kind": "SignalEvent", "expr": _ref("write_i"), "edge": "PosEdge"},
                {"kind": "SignalEvent", "expr": _ref("debug_locked_i"), "edge": "NegEdge"},
            ]},
            "stmt": {"kind": "List", "list": [{
                "kind": "Conditional",
                "conditions": [{"expr": {
                    "kind": "UnaryOp", "op": "LogicalNot",
                    "operand": _ref("debug_locked_i")}}],
                "ifTrue": _assign_procedural({"kind": "IntegerLiteral", "value": "1'b0"}),
                "ifFalse": {
                    "kind": "Conditional",
                    "conditions": [{"expr": _ref("machine_mode_i")}],
                    "ifTrue": _assign_procedural(_ref("write_i")),
                },
            }]},
        },
    })
    data = build_dependency_graph(ast, expected_top="unit")["expressions"]
    rows = [x for x in data["items"] if x.get("assignment_kind") == "procedural"]
    assert len(rows) == 2
    reset, update = sorted(rows, key=lambda x: len(x["guards"]))
    assert [g["branch"] for g in reset["guards"]] == ["then"]
    assert reset["guards"][0]["expression"]["operator"] == "LogicalNot"
    assert [g["branch"] for g in update["guards"]] == ["else", "then"]
    assert update["guards"][1]["expression"]["path"] == "unit.machine_mode_i"
    assert update["expression"]["path"] == "unit.write_i"
    for item in rows:
        assert item["coverage"] == "syntax_supported"
        assert item["nonblocking"] is True
        assert item["procedure_kind"] == "AlwaysFF"
        assert [(e["edge"], e["expression"]["path"]) for e in item["events"]] == [
            ("PosEdge", "unit.write_i"), ("NegEdge", "unit.debug_locked_i")
        ]
    assert data["counts"]["procedural_blocks_visited"] == 1


def test_normal_case_items_and_default_report_selector_and_labels():
    ast = _ast("LogicalAnd")
    members = ast["design"]["members"][0]["body"]["members"]
    members.append({
        "kind": "ProceduralBlock", "procedureKind": "AlwaysComb",
        "body": {
            "kind": "Case", "condition": "Normal", "expr": _ref("machine_mode_i"),
            "items": [{
                "expressions": [{"kind": "IntegerLiteral", "value": "1'b0"}],
                "stmt": _assign_procedural(_ref("write_i"), nb=False),
            }],
            "defaultCase": _assign_procedural(_ref("debug_locked_i"), nb=False),
        },
    })
    data = build_dependency_graph(ast, expected_top="unit")["expressions"]
    rows = [x for x in data["items"] if x.get("assignment_kind") == "procedural"]
    assert len(rows) == 2
    assert all(x["coverage"] == "syntax_supported" for x in rows)
    assert {x["guards"][0]["branch"] for x in rows} == {"item", "default"}
    case_item = next(x for x in rows if x["guards"][0]["branch"] == "item")
    assert case_item["guards"][0]["selector"]["path"] == "unit.machine_mode_i"
    assert case_item["guards"][0]["labels"][0]["value"] == "1'b0"
    assert case_item["events"] == []


def test_unsupported_timing_and_multiple_conditions_are_partial():
    ast = _ast("LogicalAnd")
    members = ast["design"]["members"][0]["body"]["members"]
    members.append({
        "kind": "ProceduralBlock", "procedureKind": "AlwaysFF",
        "body": {"kind": "Timed",
                 "timing": {"kind": "UnsupportedClocking"},
                 "stmt": {"kind": "Conditional", "conditions": [
                     {"expr": _ref("write_i")}, {"expr": _ref("machine_mode_i")}],
                     "ifTrue": _assign_procedural(_ref("write_i"))}},
    })
    data = build_dependency_graph(ast, expected_top="unit")["expressions"]
    row = next(x for x in data["items"] if x.get("assignment_kind") == "procedural")
    assert row["coverage"] == "partial"
    assert row["guards"] == [{"kind": "unsupported_guard"}]
    assert row["events"] == []


def test_unsupported_statements_are_counted_not_fabricated():
    ast = _ast("LogicalAnd")
    ast["design"]["members"][0]["body"]["members"].append({
        "kind": "ProceduralBlock", "procedureKind": "Always",
        "body": {"kind": "Wait", "condition": _ref("write_i")},
    })
    idx = build_dependency_graph(ast, expected_top="unit")["expressions"]
    assert idx["counts"]["unsupported_statements"] == 1
    assert idx["counts"]["captured"] == 1
