"""PR37: no invented field lanes for writes to packed struct members.

Synthetic slang-shaped tests are hermetic. The standalone RTL fixture also
runs through actual slang when it is installed in CI/WSL.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design


ROOT = Path(__file__).resolve().parents[1]
REAL_RTL = ROOT / "tests/fixtures/member_lvalue_pr37.sv"


def n(kind, **fields):
    return {"kind": kind, **fields}


def ref(name, address, **kw):
    return n("NamedValue", symbol=f"{address} {name}", **kw)


def field(base, member="low", address="900", **kw):
    return n("MemberAccess", value=base, member=f"{address} {member}", **kw)


def bit(base, index):
    return n("ElementSelect", value=base,
             selector=n("IntegerLiteral", value=str(index)))


def assign(lhs, rhs, nonblocking=False):
    return n("Assignment", left=lhs, right=rhs,
             isNonBlocking=nonblocking)


def synthetic(lhs, rhs, *, procedural=False, guarded=False):
    expr = assign(lhs, rhs, nonblocking=procedural)
    if guarded:
        stmt = n("Conditional", conditions=[{"expr": ref("en", "103")}],
                 ifTrue=n("ExpressionStatement", expr=expr))
    else:
        stmt = n("ExpressionStatement", expr=expr)
    if procedural:
        node = n("ProceduralBlock", procedureKind="AlwaysFF", body=stmt)
    else:
        node = n("ContinuousAssign", assignment=expr)
    return {"design": n("Root", members=[
        n("Instance", name="top",
          body=n("InstanceBody", name="top", members=[
              n("Variable", name="state", addr="101", type="logic[7:0]"),
              n("Variable", name="d", addr="102", type="logic[3:0]"),
              n("Variable", name="en", addr="103", type="logic"),
              node,
          ])),
    ])}


def graph(lhs, rhs, **kwargs):
    return build_dependency_graph(synthetic(lhs, rhs, **kwargs),
                                  expected_top="top")


def edges(g, kind):
    return {(e["source"], e["target"]) for e in g["edges"]
            if e["kind"] == kind}


def test_continuous_member_target_is_same_runtime_base_but_field_is_preserved():
    g = graph(field(ref("state", "101")), ref("d", "102"))
    assert edges(g, "data") == {("top.d", "top.state")}
    assert len(g["warnings"]) == 1
    assert "Écriture de membre" in g["warnings"][0]["reason"]
    assert g["static_selections"] == []
    row = g["expressions"]["items"][0]
    assert row["target"] == "top.state"
    assert row["coverage"] == "syntax_supported"  # syntax only
    assert row["target_write_scope"] == "whole_signal_approximation"
    assert row["target_access"] == {
        "kind": "member_access", "member": "low",
        "value": {"kind": "signal", "name": "state", "path": "top.state"},
    }
    assert g["expressions"]["counts"]["unsupported_targets"] == 0
    assert "900 low" not in json.dumps(g)


def test_nonblocking_member_write_keeps_if_guard_as_control_edge():
    g = graph(field(ref("state", "101")), ref("d", "102"),
              procedural=True, guarded=True)
    assert edges(g, "data") == {("top.d", "top.state")}
    assert edges(g, "control") == {("top.en", "top.state")}
    assert any("Écriture de membre" in w["reason"] for w in g["warnings"])
    row = g["expressions"]["items"][0]
    assert row["assignment_kind"] == "procedural"
    assert row["nonblocking"] is True
    assert row["target_write_scope"] == "whole_signal_approximation"
    assert row["guards"][0]["expression"]["path"] == "top.en"
    # register_flow must not silently claim to understand a field write.
    assert all(x["coverage"] == "partial" for x in g["register_flow"]["items"])


def test_nested_members_track_one_base_without_field_alias_invention():
    lhs = field(field(ref("state", "101"), "inner", "901"), "low", "902")
    g = graph(lhs, ref("d", "102"))
    assert edges(g, "data") == {("top.d", "top.state")}
    assert g["expressions"]["counts"]["unsupported_targets"] == 0
    a = g["expressions"]["items"][0]["target_access"]
    assert a["member"] == "low"
    assert a["value"]["member"] == "inner"
    assert a["value"]["value"]["path"] == "top.state"
    assert "target_lsb" not in json.dumps(g)


def test_member_selected_bits_are_not_reported_as_flat_signal_selections():
    lhs = bit(field(ref("state", "101")), 2)
    g = graph(lhs, ref("d", "102"))
    assert edges(g, "data") == {("top.d", "top.state")}
    assert g["static_selections"] == []
    assert any("positions de bits non démontrées" in x["reason"]
               for x in g["warnings"])
    assert g["expressions"]["items"][0]["target_write_scope"] == (
        "whole_signal_approximation"
    )


@pytest.mark.parametrize("lhs", [
    field(ref("state", "wrong")),
    n("MemberAccess", member="low", value=ref("state", "101")),
    n("MemberAccess", member="bad-name low", value=ref("state", "101")),
    n("MemberAccess", member="900 low", value=None),
    field(ref("CVA6Cfg", "999", constant="1'b1")),
])
def test_member_write_with_unproved_base_or_shape_fails_closed(lhs):
    g = graph(lhs, ref("d", "102"))
    assert not g["edges"]
    assert g["expressions"]["items"] == []
    assert g["expressions"]["counts"]["unsupported_targets"] == 1
    assert g["counts"]["warnings"] >= 1


def test_unknown_member_rhs_is_not_an_excuse_to_hide_target_write_warning():
    rhs = n("MemberAccess", member="bad", value=ref("d", "102"))
    g = graph(field(ref("state", "101")), rhs)
    assert any("MemberAccess malformé" in x["reason"] for x in g["warnings"])
    assert any("Écriture de membre" in x["reason"] for x in g["warnings"])
    assert g["expressions"]["items"][0]["coverage"] == "partial"


def test_extreme_member_nesting_is_rejected_not_unbounded():
    lhs = ref("state", "101")
    for index in range(20):
        lhs = field(lhs, f"f{index}", str(900 + index))
    g = graph(lhs, ref("d", "102"))
    assert not g["edges"]
    assert g["expressions"]["counts"]["unsupported_targets"] == 1
    assert any("profondément imbriquée" in x["reason"] for x in g["warnings"])


@pytest.mark.skipif(shutil.which("slang") is None,
                    reason="real slang v12.1 is required")
def test_real_slang_packed_struct_member_write(tmp_path):
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": "member_lvalue_pr37",
        "sources": [str(REAL_RTL)],
        "include_dirs": [],
        "defines": [],
    }), encoding="utf-8")
    result = dependency_design(load_design(manifest), tmp_path / "run",
                               timeout=120)
    assert result["status"] == "passed", result
    g = json.loads((tmp_path / "run/rtl_dependencies.json").read_text())
    assert ("member_lvalue_pr37.d", "member_lvalue_pr37.state") in edges(g, "data")
    assert ("member_lvalue_pr37.en", "member_lvalue_pr37.state") in edges(g, "control")
    assert any("Écriture de membre" in w["reason"] for w in g["warnings"])
    rows = [r for r in g["expressions"]["items"]
            if r["target"] == "member_lvalue_pr37.state"
            and r.get("target_write_scope") == "whole_signal_approximation"]
    assert rows
    assert any(r["target_access"]["kind"] == "member_access" for r in rows)
    assert g["coverage"]["design_coverage"] == "not_measured"
    assert g["bit_accesses"]["scope"] == (
        "continuous_and_supported_procedural_static_select_concat"
    )
    # This PR does not suddenly claim that procedural fields are bit-mapped.
    assert g["bit_accesses"]["counts"]["precise"] == 0
