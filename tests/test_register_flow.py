"""Tests d'exécution *syntaxique* bornée : jamais de simulation RTL."""
from __future__ import annotations

import json

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.flow import build_register_flow
from rtlprep.mcp_data import ReadOnlyRtl


def _ref(name):
    return {"kind": "NamedValue", "symbol": "1234 " + name}


def _lit(value):
    return {"kind": "IntegerLiteral", "value": value}


def _assign(rhs, line):
    return {
        "kind": "ExpressionStatement",
        "expr": {
            "kind": "Assignment",
            "left": _ref("count"),
            "right": rhs,
            "isNonBlocking": True,
            "source_file_start": "fixture.sv",
            "source_line_start": line,
        },
    }


def _ff_body(body):
    return {
        "kind": "ProceduralBlock", "procedureKind": "AlwaysFF",
        "source_file_start": "fixture.sv", "source_line_start": 6,
        "body": {
            "kind": "Timed",
            "timing": {"kind": "EventList", "events": [
                {"kind": "SignalEvent", "edge": "PosEdge", "expr": _ref("clk")},
                {"kind": "SignalEvent", "edge": "NegEdge", "expr": _ref("rst_n")},
            ]},
            "stmt": body,
        },
    }


def _ast(body, *, second=None):
    signals = ("clk", "rst_n", "enable", "count")
    members = [
        {"kind": "Port", "name": name,
         "direction": "Out" if name == "count" else "In"}
        for name in signals
    ]
    members += [{"kind": "Variable", "name": name, "type": "logic"}
                for name in signals]
    members.append(_ff_body(body))
    if second is not None:
        members.append(_ff_body(second))
    return {
        "design": {"kind": "Root", "members": [{
            "kind": "Instance", "name": "unit",
            "body": {"kind": "InstanceBody", "name": "unit",
                     "members": members},
        }]}
    }


def _if(cond, yes, no=None):
    result = {
        "kind": "Conditional", "conditions": [{"expr": cond}],
        "ifTrue": yes,
    }
    if no is not None:
        result["ifFalse"] = no
    return result


def _rows(ast):
    return build_register_flow(ast, expected_top="unit")["items"]


def test_counter_has_three_syntactic_paths_and_one_unwritten_path():
    reset = _if(
        {"kind": "UnaryOp", "op": "LogicalNot", "operand": _ref("rst_n")},
        _assign(_lit("8'd0"), 9),
        _if(_ref("enable"),
            _assign({"kind": "BinaryOp", "op": "Add",
                     "left": _ref("count"), "right": _lit("8'd1")}, 11)),
    )
    rows = _rows(_ast(reset))
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["target"] == "unit.count"
    assert row["coverage"] == "syntactic_paths_supported"
    assert row["hold_candidate"] == "syntactic_unwritten_path"
    assert row["same_path_multiple_nba"] is False
    assert row["path_count"] == 3
    assert row["events"] == [
        {"edge": "PosEdge", "signal": "unit.clk"},
        {"edge": "NegEdge", "signal": "unit.rst_n"},
    ]
    reset_path, incr_path, hold_path = row["paths"]
    assert reset_path["write_count"] == 1
    assert reset_path["guards"][0]["branch"] == "then"
    assert reset_path["guards"][0]["condition"]["operator"] == "LogicalNot"
    assert reset_path["last_nonblocking_write"]["source"]["line"] == 9
    assert [g["branch"] for g in incr_path["guards"]] == ["else", "then"]
    assert incr_path["last_nonblocking_write"]["source"]["line"] == 11
    assert [g["branch"] for g in hold_path["guards"]] == ["else", "else"]
    assert hold_path["write_count"] == 0
    assert hold_path["last_nonblocking_write"] is None


def test_last_nba_is_a_local_order_only_if_two_writes_share_a_path():
    body = {"kind": "List", "list": [
        _assign(_lit("8'd1"), 10),
        _assign(_lit("8'd2"), 11),
    ]}
    row = _rows(_ast(body))[0]
    assert row["path_count"] == 1
    assert row["hold_candidate"] == "no_unwritten_path_in_enumerated_paths"
    assert row["same_path_multiple_nba"] is True
    path = row["paths"][0]
    assert [w["order"] for w in path["writes_in_execution_order"]] == [1, 2]
    assert path["last_nonblocking_write"]["source"]["line"] == 11


def test_mutually_exclusive_writes_are_not_falsely_ranked():
    body = _if(_ref("enable"), _assign(_lit("8'd1"), 10),
               _assign(_lit("8'd2"), 11))
    row = _rows(_ast(body))[0]
    assert row["hold_candidate"] == "no_unwritten_path_in_enumerated_paths"
    assert row["same_path_multiple_nba"] is False
    assert [path["write_count"] for path in row["paths"]] == [1, 1]
    assert {path["last_nonblocking_write"]["source"]["line"]
            for path in row["paths"]} == {10, 11}


@pytest.mark.parametrize("body,reason", [
    ({"kind": "Case", "condition": "Normal", "expr": _ref("enable"),
      "items": [{"stmt": _assign(_lit("1"), 10),
                 "expressions": [_lit("1")]}]}, "unsupported_statement_Case"),
    ({"kind": "List", "list": [
        _assign(_lit("1"), 10),
        {"kind": "Wait", "condition": _ref("enable")},
    ]}, "unsupported_statement_Wait"),
    ({"kind": "ExpressionStatement", "expr": {
        "kind": "Assignment", "left": _ref("count"),
        "right": {"kind": "Call", "args": []},
        "isNonBlocking": True,
    }}, "rhs_may_have_unsupported_side_effect"),
])
def test_unknown_construct_never_proves_a_hold_or_priority(body, reason):
    graph = build_register_flow(_ast(body), expected_top="unit")
    row = graph["items"][0]
    assert row["coverage"] == "partial"
    assert row["reason"] == reason
    assert row["hold_candidate"] == "unknown"
    assert row["paths"] == []
    assert graph["counts"]["partial_processes"] == 1


@pytest.mark.parametrize("true_branch", ("missing", "null"))
def test_missing_mandatory_true_branch_is_partial_not_hold(true_branch):
    # La branche else existe pour conserver une cible détectable.
    # Un ifTrue absent ou nul ne doit jamais créer un faux chemin sans écriture.
    body = _if(_ref("enable"), _assign(_lit("8'd2"), 11),
               _assign(_lit("8'd1"), 12))
    if true_branch == "missing":
        del body["ifTrue"]
    else:
        body["ifTrue"] = None
    row = _rows(_ast(body))[0]
    assert row["coverage"] == "partial"
    assert row["reason"] == "missing_if_true_branch"
    assert row["hold_candidate"] == "unknown"
    assert row["paths"] == []


def test_optional_else_absence_remains_a_syntactic_unwritten_path():
    row = _rows(_ast(_if(_ref("enable"), _assign(_lit("8'd1"), 10))))[0]
    assert row["coverage"] == "syntactic_paths_supported"
    assert row["path_count"] == 2
    assert row["hold_candidate"] == "syntactic_unwritten_path"
    assert sorted(p["write_count"] for p in row["paths"]) == [0, 1]


def test_path_explosion_degrades_to_partial_not_a_fake_result():
    node = _assign(_lit("0"), 20)
    for _ in range(7):
        node = _if(_ref("enable"), node, node)
    graph = build_register_flow(_ast(node), expected_top="unit")
    assert graph["items"][0]["coverage"] == "partial"
    assert graph["items"][0]["hold_candidate"] == "unknown"


def test_multiple_processes_are_separate_and_not_cross_ranked():
    row = _rows(_ast(_assign(_lit("1"), 10),
                     second=_assign(_lit("2"), 20)))
    assert len(row) == 2
    assert row[0]["process"] != row[1]["process"]
    assert all(x["same_path_multiple_nba"] is False for x in row)
    assert all(x["path_count"] == 1 for x in row)


def test_read_only_mcp_serves_stored_flow_with_pagination(tmp_path):
    graph = build_dependency_graph(_ast(_assign(_lit("1"), 10)),
                                   expected_top="unit")
    graph["source_fingerprint"] = "snapshot_r"
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    api = ReadOnlyRtl(graph_file=path)
    assert api.capabilities()["register_flow_available"] is True
    resp = api.register_flow("unit.count", limit=1)
    assert resp["total"] == 1
    assert resp["source_snapshot_status"] == "unverifiable"
    assert resp["items"][0]["paths"][0]["write_count"] == 1
    assert api.register_flow("unit.enable")["total"] == 0
    for limit, offset in ((0, 0), (101, 0), (1, -1)):
        with pytest.raises(ValueError):
            api.register_flow("unit.count", limit=limit, offset=offset)
    with pytest.raises(KeyError):
        api.register_flow("../arbitrary/file")
    del graph["register_flow"]
    path.write_text(json.dumps(graph), encoding="utf-8")
    older = ReadOnlyRtl(graph_file=path)
    assert older.capabilities()["register_flow_available"] is False
    with pytest.raises(ValueError, match="régénérer"):
        older.register_flow("unit.count")


def test_flows_do_not_exist_for_continuous_assignments():
    ast = _ast(_assign(_lit("1"), 10))
    ast["design"]["members"][0]["body"]["members"].pop()
    ast["design"]["members"][0]["body"]["members"].append({
        "kind": "ContinuousAssign",
        "assignment": {"kind": "Assignment", "left": _ref("count"),
                       "right": _ref("enable")},
    })
    data = build_register_flow(ast, expected_top="unit")
    assert data["items"] == []
