"""PR36: semantic MemberAccess without false runtime edges or coverage claims."""
from __future__ import annotations

import json
import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.symbols import member_name


def n(kind, **kwargs):
    return {"kind": kind, **kwargs}


def ref(name, addr, **kwargs):
    return n("NamedValue", symbol=f"{addr} {name}", **kwargs)


def member(value, name="Enabled", addr="777", **kwargs):
    return n("MemberAccess", value=value, member=f"{addr} {name}", **kwargs)


def lit(value="1'b1"):
    return n("IntegerLiteral", value=value)


def stmt(lhs, rhs):
    return n("ExpressionStatement", expr=n(
        "Assignment", left=lhs, right=rhs, isNonBlocking=False,
    ))


def design(rhs=None, *, procedural=False, initial=False):
    if rhs is None:
        rhs = member(ref("CVA6Cfg", "900", constant="18'h3"), constant="1'b1")
    if initial:
        logic = n("ProceduralBlock", procedureKind="Initial",
                  body=stmt(ref("out", "102"), rhs))
    elif procedural:
        logic = n("ProceduralBlock", procedureKind="AlwaysComb",
                  body=stmt(ref("out", "102"), rhs))
    else:
        logic = n("ContinuousAssign", assignment=n(
            "Assignment", left=ref("out", "102"),
            right=rhs, isNonBlocking=False,
        ))
    return {"design": n("Root", members=[
        n("Instance", name="top", body=n("InstanceBody", name="top", members=[
            n("Parameter", name="CVA6Cfg", addr="900", type="struct"),
            n("Variable", name="bundle", addr="101", type="logic[7:0]"),
            n("Variable", name="out", addr="102", type="logic[7:0]"),
            logic,
        ])),
    ])}


def graph(rhs=None, **kwargs):
    return build_dependency_graph(design(rhs, **kwargs), expected_top="top")


def edges(g, kind="data"):
    return {(e["source"], e["target"]) for e in g["edges"]
            if e["kind"] == kind}


def expr(g):
    return g["expressions"]["items"][0]


def test_semantic_member_parser_keeps_only_name_and_rejects_bad_tokens():
    assert member_name(member(ref("bundle", "101"), addr="321")) == "Enabled"
    for bad in ("Enabled", "abc Enabled", "123 ", "123 illegal.name",
                "9 foo bar", "1 " + "X" * 200, 12, None):
        assert member_name(n("MemberAccess", member=bad)) is None


def test_config_parameter_field_is_expression_not_runtime_signal():
    g = graph()
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert g["edges"] == []
    record = expr(g)
    assert record["coverage"] == "syntax_supported"
    assert record["expression"] == {
        "kind": "member_access", "member": "Enabled",
        "value": {"kind": "constant_reference", "name": "CVA6Cfg"},
    }
    assert g["expressions"]["counts"]["partial_expressions"] == 0
    assert "777 Enabled" not in json.dumps(g)
    assert "900 CVA6Cfg" not in json.dumps(g)


def test_member_field_on_real_runtime_struct_is_whole_signal_dependency():
    g = graph(member(ref("bundle", "101"), name="ready", constant="1'b0"),
              procedural=True)
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert edges(g) == {("top.bundle", "top.out")}
    record = expr(g)
    assert record["coverage"] == "syntax_supported"
    assert record["expression"]["member"] == "ready"
    assert record["expression"]["value"] == {
        "kind": "signal", "name": "bundle", "path": "top.bundle",
    }
    assert record["assignment_kind"] == "procedural"


def test_nested_runtime_member_access_tracks_base_without_flattening():
    inner = member(ref("bundle", "101"), name="inner")
    outer = member(inner, name="bit")
    g = graph(outer)
    assert edges(g) == {("top.bundle", "top.out")}
    assert g["counts"]["warnings"] == 0
    ast = expr(g)["expression"]
    assert ast["kind"] == "member_access"
    assert ast["member"] == "bit"
    assert ast["value"]["member"] == "inner"
    assert ast["value"]["value"]["path"] == "top.bundle"
    assert "target_lsb" not in json.dumps(g)


def test_constant_property_cannot_hide_dependency_on_known_runtime_signal():
    rhs = member(ref("bundle", "101", constant="8'h00"),
                 name="ready", constant="1'b0")
    g = graph(rhs)
    assert edges(g) == {("top.bundle", "top.out")}
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert expr(g)["expression"]["value"]["kind"] == "signal"
    assert expr(g)["coverage"] == "syntax_supported"


def test_unknown_symbol_address_fails_closed_even_with_known_name():
    g = graph(member(ref("bundle", "wrong", constant="8'h0")))
    assert not edges(g)
    assert g["counts"]["warnings"] > 0, g
    assert expr(g)["coverage"] == "partial"
    assert expr(g)["expression"]["value"]["kind"] == "unsupported"


@pytest.mark.parametrize("raw", [
    "Enabled", "abc Enabled", "123 illegal.name", "777 ",
])
def test_malformed_member_access_keeps_warning_and_partial(raw):
    rhs = n("MemberAccess", member=raw, value=ref("bundle", "101"))
    g = graph(rhs)
    assert g["counts"]["warnings"] > 0
    assert edges(g) == set()
    assert expr(g)["coverage"] == "partial"
    assert expr(g)["expression"] == {
        "kind": "unsupported", "ast_kind": "malformed_member_access",
    }


def test_missing_member_base_is_not_marked_supported():
    g = graph(n("MemberAccess", member="777 Enabled"))
    assert g["counts"]["warnings"] > 0
    assert expr(g)["coverage"] == "partial"
    assert expr(g)["expression"]["kind"] == "unsupported"


def test_constant_initial_member_is_metadata_only_and_runtime_member_is_not():
    constant = graph(initial=True)
    assert len(constant["initializations"]) == 1
    assert constant["edges"] == []
    assert constant["counts"]["warnings"] == 0
    runtime = graph(member(ref("bundle", "101")), initial=True)
    assert runtime["initializations"] == []
    assert runtime["edges"] == []
    assert any("Initial" in w["reason"] for w in runtime["warnings"])


def test_member_access_lvalue_is_still_outside_current_support():
    lhs = member(ref("bundle", "101"), name="ready")
    ast = design()
    ast["design"]["members"][0]["body"]["members"][-1] = n(
        "ContinuousAssign", assignment=n(
            "Assignment", left=lhs, right=lit(), isNonBlocking=False,
        ),
    )
    g = build_dependency_graph(ast, expected_top="top")
    assert g["edges"] == []
    assert any("Cible non prise en charge" in w["reason"] for w in g["warnings"])
    assert g["expressions"]["counts"]["unsupported_targets"] == 1


def test_member_base_in_if_guard_is_control_dependency_not_spurious_data():
    clause = n("Conditional", conditions=[
        {"expr": member(ref("bundle", "101"))},
    ], ifTrue=stmt(ref("out", "102"), lit()),
       ifFalse=stmt(ref("out", "102"), lit("1'b0")))
    ast = design(procedural=True)
    ast["design"]["members"][0]["body"]["members"][-1]["body"] = clause
    g = build_dependency_graph(ast, expected_top="top")
    assert edges(g, "control") == {("top.bundle", "top.out")}
    assert g["counts"]["warnings"] == 0, g["warnings"]
    rows = g["expressions"]["items"]
    assert len(rows) == 2
    assert all(e["coverage"] == "syntax_supported" for e in rows)
    assert all(e["guards"][0]["expression"]["kind"] == "member_access"
               for e in rows)
