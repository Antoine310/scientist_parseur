"""PR #24 : transitions possibles, motifs reset et priorité locale sans simulation."""
from __future__ import annotations

import copy
import json

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.flow import build_register_flow
from rtlprep.mcp_data import ReadOnlyRtl
from rtlprep.sequential import build_sequential_candidates


def n(kind, **kwargs):
    return {"kind": kind, **kwargs}


def ref(name):
    return n("NamedValue", symbol="1234 " + name)


def lit(value):
    return n("IntegerLiteral", value=value)


def assign(value, line):
    return n("ExpressionStatement", expr=n(
        "Assignment", left=ref("q"), right=value, isNonBlocking=True,
        source_file_start="state.sv", source_line_start=line,
    ))


def cond(signal, yes, no=None):
    x = n("Conditional", conditions=[{"expr": signal}], ifTrue=yes)
    if no is not None:
        x["ifFalse"] = no
    return x


def neg(value):
    return n("UnaryOp", op="LogicalNot", operand=value)


def ast(body, *, extra=None, events=None):
    if events is None:
        events = [("clk", "PosEdge"), ("rst_n", "NegEdge")]
    def block(inner):
        return n("ProceduralBlock", procedureKind="AlwaysFF", body=n(
            "Timed", timing=n("EventList", events=[
                n("SignalEvent", edge=edge, expr=ref(name))
                for name, edge in events
            ]), stmt=inner
        ))
    members = [n("Variable", name=name, type="logic")
               for name in ("clk", "rst_n", "en", "q")]
    members.append(block(body))
    if extra is not None:
        members.append(block(extra))
    return {"design": n("Root", members=[
        n("Instance", name="unit", body=n(
            "InstanceBody", name="unit", members=members))
    ])}


def seq(value):
    flow = build_register_flow(value, expected_top="unit")
    return build_sequential_candidates(flow)


def test_reset_like_candidate_and_rhs_are_explicit_syntax_not_simulation():
    body = cond(neg(ref("rst_n")), assign(lit("8'd0"), 9),
                cond(ref("en"), assign(n("BinaryOp", op="Add",
                          left=ref("q"), right=lit("8'd1")), 11)))
    result = seq(ast(body))
    row = result["items"][0]
    assert row["coverage"] == "syntactic_candidates_supported"
    assert row["reset_like_detection"] == "candidate_found"
    assert len(row["paths"]) == 3
    reset, increment, hold = row["paths"]
    guard = reset["reset_like_guard_candidate"]
    assert guard == {
        "signal": "unit.rst_n", "edge": "NegEdge",
        "asserted_level": "low", "literal_write": "8'd0",
        "classification": "reset_like_guard_candidate_not_proof",
    }
    assert reset["transition_candidate"]["rhs"] == {
        "kind": "literal", "value": "8'd0"
    }
    assert increment["reset_like_guard_candidate"] is None
    assert increment["transition_candidate"]["rhs"]["kind"] == "binary"
    assert increment["transition_candidate"]["rhs"]["operator"] == "Add"
    assert hold["transition_candidate"] == {
        "kind": "unwritten_in_this_process"
    }
    assert result["counts"]["unwritten_paths"] == 1
    assert result["counts"]["reset_like_candidate_paths"] == 1
    assert "proof" in result["caveat"] or "preuve" in result["caveat"]


def test_reset_like_candidate_preserves_explicit_slang_conversion():
    # Slang v12.1: assignment RHS may wrap an integer in Conversion.
    wrapped = n("Conversion", operand=lit("8'd0"))
    body = cond(neg(ref("rst_n")), assign(wrapped, 9))
    row = seq(ast(body))["items"][0]
    candidate = row["paths"][0]["reset_like_guard_candidate"]
    assert candidate is not None
    assert candidate["literal_write"] == "8'd0"
    assert candidate["rhs_conversion_kinds"] == ["Conversion"]
    assert row["paths"][0]["transition_candidate"]["rhs"]["kind"] == "conversion"


def test_last_nba_only_orders_writes_in_same_path():
    body = n("List", list=[assign(lit("8'd1"), 12),
                           assign(lit("8'd2"), 13)])
    row = seq(ast(body))["items"][0]
    path = row["paths"][0]
    assert path["write_count"] == 2
    assert path["local_overwritten_orders"] == [1]
    assert path["transition_candidate"]["write_order"] == 2
    assert path["transition_candidate"]["rhs"]["value"] == "8'd2"
    assert row["priority_scope"] == "same_process_and_syntactic_path_only"
    assert row["reset_like_detection"] == "none_matched_in_supported_paths"


def test_mutually_exclusive_branches_are_not_ranked_as_local_overwrites():
    row = seq(ast(cond(ref("en"), assign(lit("8'd1"), 12),
                       assign(lit("8'd2"), 13))))["items"][0]
    assert len(row["paths"]) == 2
    assert all(p["local_overwritten_orders"] == [] for p in row["paths"])


def test_no_reset_is_inferred_with_single_clock_event():
    row = seq(ast(
        cond(ref("clk"), assign(lit("8'd0"), 12)),
        events=[("clk", "PosEdge")]
    ))["items"][0]
    assert row["reset_like_detection"] == "none_matched_in_supported_paths"
    assert all(p["reset_like_guard_candidate"] is None for p in row["paths"])


def test_else_branch_can_be_reset_like_when_guard_is_active_high():
    # if (rst_n) q <= q + 1; else q <= 0; @(posedge clk or negedge rst_n)
    body = cond(ref("rst_n"),
                assign(n("BinaryOp", op="Add",
                         left=ref("q"), right=lit("1")), 12),
                assign(lit("0"), 13))
    row = seq(ast(body))["items"][0]
    assert row["reset_like_detection"] == "candidate_found"
    assert row["paths"][0]["reset_like_guard_candidate"] is None
    assert row["paths"][1]["reset_like_guard_candidate"]["asserted_level"] == "low"


def test_processes_same_target_are_flagged_without_cross_process_priority():
    rows = seq(ast(assign(lit("1"), 1), extra=assign(lit("2"), 2)))["items"]
    assert len(rows) == 2
    assert all(row["multiple_processes_same_target"] for row in rows)
    assert all(row["paths"][0]["local_overwritten_orders"] == [] for row in rows)
    assert rows[0]["process"] != rows[1]["process"]


def test_partial_procedure_has_no_transition_candidates():
    body = n("List", list=[assign(lit("1"), 12), n("Wait", expr=ref("en"))])
    row = seq(ast(body))["items"][0]
    assert row["coverage"] == "partial"
    assert row["paths"] == []
    assert row["reset_like_detection"] == "unknown"
    assert row["reason"] == "unsupported_statement_Wait"


def test_unknown_rhs_reference_never_becomes_known_transition():
    row = seq(ast(assign(ref("unknown_parameter"), 12)))["items"][0]
    assert row["coverage"] == "syntactic_candidates_supported"
    assert row["paths"][0]["transition_candidate"]["kind"] == "unknown_rhs"
    assert row["reset_like_detection"] == "none_matched_in_supported_paths"


@pytest.mark.parametrize("invalid", [
    lambda data: data.update(schema_version=2),
    lambda data: data["counts"].update(truncated="false"),
    lambda data: data["items"][0]["paths"][0].update(write_count=900),
    lambda data: data["items"][0]["paths"][0].update(writes_in_execution_order=None),
])
def test_malformed_or_bounded_flow_never_yields_fabricated_candidate(invalid):
    data = build_register_flow(ast(assign(lit("1"), 12)), expected_top="unit")
    invalid(data)
    if data.get("schema_version") != 1 or type(data["counts"]["truncated"]) is not bool:
        with pytest.raises(ValueError):
            build_sequential_candidates(data)
    else:
        row = build_sequential_candidates(data)["items"][0]
        assert row["coverage"] == "partial"
        assert row["paths"] == []
        assert row["reset_like_detection"] == "unknown"


def test_mcp_snapshot_pagination_exact_filter_and_legacy(tmp_path):
    graph = build_dependency_graph(ast(assign(lit("1"), 12)),
                                   expected_top="unit")
    file = tmp_path / "rtl_dependencies.json"
    file.write_text(json.dumps(graph), encoding="utf-8")
    api = ReadOnlyRtl(graph_file=file)
    assert api.capabilities()["sequential_candidates_available"] is True
    result = api.sequential_candidates("unit.q", limit=1)
    assert result["total"] == 1
    assert result["source_snapshot_status"] == "unverifiable"
    assert result["items"][0]["coverage"] == "syntactic_candidates_supported"
    assert api.sequential_candidates("unit.en")["total"] == 0
    for limit, offset in ((0, 0), (101, 0), (1, -1), (True, 0)):
        with pytest.raises(ValueError):
            api.sequential_candidates("unit.q", limit, offset)
    with pytest.raises(KeyError):
        api.sequential_candidates("../escape")
    without = copy.deepcopy(graph)
    del without["sequential_candidates"]
    file.write_text(json.dumps(without), encoding="utf-8")
    old = ReadOnlyRtl(graph_file=file)
    assert old.capabilities()["sequential_candidates_available"] is False
    with pytest.raises(ValueError, match="régénérer"):
        old.sequential_candidates("unit.q")
