"""PR #32: concatenated procedural lvalues, conservative per-bit dependencies."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.field_validation import git_blob_sha1
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design

ROOT = Path(__file__).resolve().parents[1]
RXUART = ROOT / "upstream_unknown/wbuart32/rtl/rxuart.v"
RXUART_PIN = "1506e563944a2da1c1b01be6c1a953ad92fdff7d"


def n(kind, **kwargs):
    return {"kind": kind, **kwargs}


def ref(name, address="123"):
    return n("NamedValue", symbol=f"{address} {name}")


def scalar(name):
    return n("Variable", name=name, type="logic")


def concat(*values):
    return n("Concatenation", operands=list(values))


def statement(lhs, rhs):
    return n("ExpressionStatement", expr=n(
        "Assignment", left=lhs, right=rhs, isNonBlocking=True,
    ))


def synthetic(stmt, *, extra=None):
    body = [scalar(s) for s in (
        "i_clk", "i_reset", "i_uart_rx", "q_uart", "qq_uart", "ck_uart"
    )]
    body.extend(extra or [])
    body.append(n("ProceduralBlock", procedureKind="Always", body=n(
        "Timed", timing=n("SignalEvent", edge="PosEdge", expr=ref("i_clk")),
        stmt=stmt,
    )))
    return {"design": n("Root", members=[
        n("Instance", name="top", body=n("InstanceBody", name="top", members=body))
    ])}


def links(graph, kind):
    return {(e["source"], e["target"]) for e in graph["edges"] if e["kind"] == kind}


def test_positional_scalar_lvalue_mapping_no_cross_lane_dependencies():
    lhs = concat(ref("ck_uart"), ref("qq_uart"), ref("q_uart"))
    rhs = concat(ref("qq_uart"), ref("q_uart"), ref("i_uart_rx"))
    tree = synthetic(n("Conditional", conditions=[{"expr": ref("i_reset")}],
        ifTrue=statement(lhs, n("IntegerLiteral", value="3'h0")),
        ifFalse=statement(lhs, rhs)))
    graph = build_dependency_graph(tree, expected_top="top")
    assert links(graph, "data") == {
        ("top.qq_uart", "top.ck_uart"),
        ("top.q_uart", "top.qq_uart"),
        ("top.i_uart_rx", "top.q_uart"),
    }
    assert links(graph, "control") == {
        ("top.i_reset", "top.ck_uart"),
        ("top.i_reset", "top.qq_uart"),
        ("top.i_reset", "top.q_uart"),
    }
    assert links(graph, "event") == {
        ("top.i_clk", "top.ck_uart"),
        ("top.i_clk", "top.qq_uart"),
        ("top.i_clk", "top.q_uart"),
    }
    assert all(e["sequential"] and e["detail"] == "PosEdge"
               for e in graph["edges"] if e["kind"] == "event")
    assert graph["counts"]["warnings"] == 0, graph["warnings"]


def test_unsupported_multi_bit_lane_keeps_events_but_never_guesses_data():
    lhs = concat(ref("ck_uart"), ref("bus"))
    rhs = concat(ref("qq_uart"), ref("wide"))
    tree = synthetic(statement(lhs, rhs), extra=[
        n("Variable", name="bus", type="logic[7:0]"),
        n("Variable", name="wide", type="logic[7:0]"),
    ])
    graph = build_dependency_graph(tree, expected_top="top")
    assert links(graph, "data") == set()
    assert links(graph, "event") == {
        ("top.i_clk", "top.ck_uart"), ("top.i_clk", "top.bus"),
    }
    assert any("positions RHS non démontrées" in w["reason"]
               for w in graph["warnings"])


@pytest.mark.parametrize("bad_lhs", [
    n("Concatenation", operands=[]),
    n("Concatenation", operands=[ref("ck_uart"), n("ElementSelect",
        value=ref("q_uart"), selector=n("IntegerLiteral", value="0"))]),
    n("Concatenation", operands=[ref("ck_uart"), ref("missing")]),
])
def test_invalid_lvalue_is_rejected_atomically_without_partial_edges(bad_lhs):
    graph = build_dependency_graph(synthetic(
        statement(bad_lhs, concat(ref("qq_uart"), ref("q_uart")))
    ), expected_top="top")
    assert not graph["edges"]
    assert graph["counts"]["warnings"] >= 1


def test_wrong_ast_identity_is_not_resolved_by_a_similar_name():
    lhs = concat(ref("ck_uart", "wrong_address"), ref("qq_uart"))
    tree = synthetic(statement(lhs, concat(ref("qq_uart"), ref("q_uart"))))
    declarations = tree["design"]["members"][0]["body"]["members"]
    next(node for node in declarations if node.get("name") == "ck_uart")["addr"] = "actual_address"
    graph = build_dependency_graph(tree, expected_top="top")
    assert not graph["edges"]
    assert any("non résolu" in w["reason"] for w in graph["warnings"])


def test_ambiguous_rhs_is_partial_with_event_but_without_fabricated_data():
    lhs = concat(ref("ck_uart"), ref("q_uart"))
    rhs = n("BinaryOp", op="Add", left=ref("qq_uart"),
            right=n("IntegerLiteral", value="2'd1"))
    graph = build_dependency_graph(synthetic(statement(lhs, rhs)),
                                   expected_top="top")
    assert not links(graph, "data")
    assert links(graph, "event") == {
        ("top.i_clk", "top.ck_uart"), ("top.i_clk", "top.q_uart"),
    }
    assert any("données omises" in w["reason"] for w in graph["warnings"])


def test_constant_rhs_never_creates_signal_data_edges_even_if_width_differs():
    lhs = concat(ref("ck_uart"), ref("q_uart"))
    graph = build_dependency_graph(synthetic(
        statement(lhs, n("IntegerLiteral", value="3'h0"))
    ), expected_top="top")
    assert not links(graph, "data")
    assert len(links(graph, "event")) == 2
    assert graph["counts"]["warnings"] == 0


@pytest.mark.skipif(shutil.which("slang") is None, reason="slang réel absent")
@pytest.mark.skipif(not RXUART.is_file(), reason="checkout épinglé rxuart absent")
def test_real_pinned_rxuart_concat_lvalue_dependencies(tmp_path):
    """Real slang 12.1 + unchanged ZipCPU RTL: check observed exact lanes."""
    assert git_blob_sha1(RXUART.read_bytes()) == RXUART_PIN
    design_path = tmp_path / "design.json"
    design_path.write_text(json.dumps({
        "top": "rxuart", "sources": [str(RXUART)],
        "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "report"
    result = dependency_design(load_design(design_path), out, 90)
    assert result["status"] == "passed", result
    graph = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
    assert {
        ("rxuart.qq_uart", "rxuart.ck_uart"),
        ("rxuart.q_uart", "rxuart.qq_uart"),
        ("rxuart.i_uart_rx", "rxuart.q_uart"),
    }.issubset(links(graph, "data")), graph["warnings"]
    for signal in ("ck_uart", "qq_uart", "q_uart"):
        assert ("rxuart.i_clk", f"rxuart.{signal}") in links(graph, "event")
    assert not any(
        "Cible non prise en charge : Concatenation" in w["reason"]
        for w in graph["warnings"]
    ), graph["warnings"]
    # No claim about complete analysis of all the UART constructs.
