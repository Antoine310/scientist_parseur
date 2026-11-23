"""PR38: procedural bit slices are positional syntax, not sequential proofs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep import bitaccess
from rtlprep.bitaccess import build_bit_access_index
from rtlprep.dependencies import build_dependency_graph
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests/fixtures/procedural_bit_pr38.sv"


def n(kind, **props):
    return {"kind": kind, **props}


def ref(name, address=None, **kwargs):
    ids = {"a": "100", "q": "101", "en": "102",
           "clk": "103", "rst_n": "104", "idx": "105", "mode": "106"}
    return n("NamedValue", symbol=f"{address or ids[name]} {name}", **kwargs)


def lit(value):
    return n("IntegerLiteral", value=str(value))


def sl(base, high, low):
    return n("RangeSelect", value=base, left=lit(high), right=lit(low))


def bit(base, selector):
    return n("ElementSelect", value=base, selector=selector)


def ass(lhs, rhs, *, nb=False):
    return n("ExpressionStatement", expr=n(
        "Assignment", left=lhs, right=rhs, isNonBlocking=nb,
    ))


def proc(body, kind="AlwaysComb"):
    return n("ProceduralBlock", procedureKind=kind, body=body)


def timed(body, *, explicit=False):
    if explicit:
        timing = n("EventList", events=[
            n("SignalEvent", edge="PosEdge", expr=ref("clk")),
            n("SignalEvent", edge="NegEdge", expr=ref("rst_n")),
        ])
    else:
        timing = n("ImplicitEvent")
    return n("Timed", timing=timing, stmt=body)


def design(*items):
    names = {"a": "100", "q": "101", "en": "102",
             "clk": "103", "rst_n": "104", "idx": "105", "mode": "106"}
    declarations = [n("Variable", name=name, addr=address, type="logic[7:0]")
                    for name, address in names.items()]
    return {"design": n("Root", members=[
        n("Instance", name="top",
          body=n("InstanceBody", name="top",
                 members=declarations + list(items))),
    ])}


def rows(ast):
    return build_bit_access_index(ast, expected_top="top")


def test_ff_range_write_has_explicit_lanes_nonblocking_guard_and_events():
    expr = ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4), nb=True)
    guarded = n("Conditional", conditions=[{"expr": ref("en")}],
                ifTrue=expr)
    result = rows(design(proc(timed(guarded, explicit=True), "AlwaysFF")))
    assert result["scope"] == "continuous_and_supported_procedural_static_select_concat"
    assert result["counts"]["captured"] == 1, result
    assert result["counts"]["precise"] == 1
    row = result["items"][0]
    assert row["target"] == "top.q"
    assert row["coverage"] == "explicit_target_lanes"
    assert row["target_selection"] == {"kind": "range", "msb": 3, "lsb": 0}
    assert row["source_segments"] == [{
        "source": "top.a", "selection": {"kind": "range", "msb": 7, "lsb": 4},
        "rhs_lsb": 0, "rhs_msb": 3, "target_lsb": 0, "target_msb": 3,
    }]
    assert row["procedure_kind"] == "AlwaysFF"
    assert row["nonblocking"] is True
    assert row["assignment_kind"] == "procedural"
    assert row["guards"] == [{
        "kind": "if", "branch": "then", "condition_ast_kind": "NamedValue"
    }]
    assert row["timing_scope"] == "explicit_event_syntax"
    assert row["events"] == [
        {"edge": "PosEdge", "signal": "top.clk"},
        {"edge": "NegEdge", "signal": "top.rst_n"},
    ]


def test_comb_case_paths_are_separate_and_implicit_event_not_guessed():
    left = sl(ref("q"), 1, 0)
    clause = n("Case", condition="Normal", expr=ref("mode"),
               items=[{"expressions": [lit("2'd1")],
                       "stmt": ass(left, sl(ref("a"), 3, 2))}],
               defaultCase=ass(left, sl(ref("a"), 1, 0)))
    report = rows(design(proc(timed(n("List", list=[clause])))))
    assert report["counts"]["captured"] == 2
    assert report["counts"]["precise"] == 2
    assert {x["guards"][0]["branch"] for x in report["items"]} == {
        "item", "default",
    }
    assert all(x["timing_scope"] == "implicit_not_expanded"
               and x["events"] == []
               and x["nonblocking"] is False
               and x["coverage"] == "explicit_target_lanes"
               for x in report["items"])


def test_plain_comb_rhs_selection_produces_rhs_only_lanes():
    report = rows(design(proc(timed(ass(ref("q"), sl(ref("a"), 3, 0))))))
    assert report["counts"]["precise"] == 1
    item = report["items"][0]
    assert item["coverage"] == "rhs_lanes_only"
    assert item["target_selection"] == {"kind": "whole"}
    assert "target_lsb" not in item["source_segments"][0]


def test_dynamic_index_remains_partial_in_procedural_assignment():
    lhs = bit(ref("q"), ref("idx", constant="2"))
    report = rows(design(proc(ass(lhs, bit(ref("a"), lit(5))))))
    assert report["counts"]["partial"] == 1
    item = report["items"][0]
    assert item["coverage"] == "partial"
    assert item["reason"] == "dynamic_or_unknown_index"
    assert item["source_segments"] == []


def test_unproven_conversion_and_arithmetic_remain_partial():
    for value in (
        n("Conversion", operand=sl(ref("a"), 3, 0)),
        n("BinaryOp", op="Add", left=sl(ref("a"), 3, 0), right=lit(1)),
    ):
        result = rows(design(proc(ass(sl(ref("q"), 3, 0), value))))
        assert result["counts"]["partial"] == 1
        assert result["items"][0]["source_segments"] == []
        assert result["items"][0]["coverage"] == "partial"


def test_bad_guard_makes_bit_record_partial_even_if_lanes_are_static():
    invalid = n("Conditional", conditions=[
        {"expr": ref("en")}, {"expr": ref("mode")},
    ], ifTrue=ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4)))
    report = rows(design(proc(invalid)))
    assert report["counts"]["unsupported_statements"] == 1
    assert report["counts"]["partial"] == 1
    item = report["items"][0]
    assert item["coverage"] == "partial"
    assert item["reason"] == "unsupported_procedural_context"
    assert item["guards"][0]["kind"] == "unsupported_guard"


def test_bad_timing_keeps_explicit_context_limit_not_fake_event_edges():
    bad = n("Timed", timing=n("SignalEvent", edge="Unexpected",
                              expr=ref("clk")),
            stmt=ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4), nb=True))
    report = rows(design(proc(bad, "AlwaysFF")))
    assert report["counts"]["partial"] == 1
    item = report["items"][0]
    assert item["events"] == []
    assert item["timing_scope"] == "unsupported_timing"
    assert item["reason"] == "unsupported_procedural_context"


def test_wrong_identity_lhs_rejected_in_procedural_scope():
    bad = sl(ref("q", address="999"), 3, 0)
    report = rows(design(proc(ass(bad, sl(ref("a"), 7, 4)))))
    assert report["counts"]["unsupported_targets"] == 1
    assert report["items"] == []


def test_member_access_in_procedure_with_bit_slice_is_explicitly_excluded():
    lhs = n("MemberAccess", value=ref("q"), member="333 low")
    report = rows(design(proc(ass(lhs, sl(ref("a"), 3, 0)))))
    assert report["counts"]["unsupported_targets"] == 1
    assert report["items"] == []


def test_unknown_statement_is_counted_in_coverage_not_silently_ignored():
    tree = design(proc(n("List", list=[
        n("ForLoop", body=ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4))),
        ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4)),
    ])))
    g = build_dependency_graph(tree, expected_top="top")
    assert g["bit_accesses"]["counts"]["unsupported_statements"] == 1
    assert g["bit_accesses"]["counts"]["captured"] == 1
    assert g["coverage"]["analyzers"]["bit_accesses"]["assessment"] == "reported_limits"
    assert (g["coverage"]["analyzers"]["bit_accesses"]["excluded_from_records"]
            ["unsupported_statements"] == 1)


def test_unsupported_initial_is_explicitly_counted_not_treated_as_always():
    report = rows(design(proc(
        ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4)), "Initial")))
    assert report["counts"]["captured"] == 0
    assert report["counts"]["procedural_blocks_skipped"] == 1


def test_bounded_procedural_statement_walk_reports_truncation(monkeypatch):
    monkeypatch.setattr(bitaccess, "MAX_PROC_STATEMENTS", 2)
    tree = design(proc(n("List", list=[
        ass(sl(ref("q"), 3, 0), sl(ref("a"), 7, 4))
    ])))
    result = rows(tree)
    assert result["counts"]["truncated"] is True
    assert result["counts"]["unsupported_statements"] >= 1
    assert result["counts"]["precise"] == 0


def test_continuous_assign_regression_not_reclassified_as_procedural():
    statement = n("ContinuousAssign", assignment=ass(
        sl(ref("q"), 3, 0), sl(ref("a"), 7, 4))["expr"])
    report = rows(design(statement))
    item = report["items"][0]
    assert item["coverage"] == "explicit_target_lanes"
    assert "procedure_kind" not in item
    assert "guards" not in item
    assert report["counts"]["precise"] == 1


@pytest.mark.skipif(shutil.which("slang") is None, reason="real slang unavailable")
def test_real_slang_ff_and_comb_bit_slices(tmp_path):
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": "procedural_bit_pr38",
        "sources": [str(REAL)],
        "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "run"
    res = dependency_design(load_design(manifest), out, timeout=120)
    assert res["status"] == "passed", res
    graph = json.loads((out / "rtl_dependencies.json").read_text())
    report = graph["bit_accesses"]
    assert report["counts"]["procedural_blocks_visited"] == 2, report
    assert report["counts"]["captured"] >= 3, report
    assert any(x["procedure_kind"] == "AlwaysFF" and
               x["target"] == "procedural_bit_pr38.reg_q" and
               x["coverage"] == "explicit_target_lanes"
               for x in report["items"]), report
    assert any(x["procedure_kind"] == "AlwaysComb" and
               x["target"] == "procedural_bit_pr38.comb_q"
               for x in report["items"])
    assert any(x["guards"] for x in report["items"])
    assert graph["coverage"]["design_coverage"] == "not_measured"
    assert graph["coverage"]["analyzers"]["bit_accesses"]["scope"] == (
        "continuous_and_supported_procedural_static_select_concat"
    )
