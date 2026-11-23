"""Contrôle temporel slang: sensibilités implicites et événements explicites.

Un événement d'horloge ne se déduit pas de always @*: seulement des fronts
PosEdge/NegEdge explicites portant une identité de signal résolue.
"""
from __future__ import annotations

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.expressions import build_expression_index


def node(kind, **fields):
    return {"kind": kind, **fields}


def named(address, name):
    return node("NamedValue", symbol=f"{address} {name}")


def process(kind, *, edge="PosEdge", ref_address=10, procedure="Always",
            multi=False, nonblocking=True):
    if kind == "implicit":
        timing = node("ImplicitEvent")
    elif kind == "direct":
        timing = node("SignalEvent", edge=edge, expr=named(ref_address, "clk"))
    elif kind == "list":
        timing = node("EventList", events=[
            node("SignalEvent", edge=edge, expr=named(ref_address, "clk")),
        ])
    elif kind == "broken-list":
        timing = node("EventList", events=[node("UnknownEvent")])
    elif kind == "empty-list":
        timing = node("EventList", events=[])
    elif kind == "unsupported":
        timing = node("CycleDelay", count=1)
    else:
        raise AssertionError(kind)
    statement = node("ExpressionStatement", expr=node(
        "Assignment", left=named(30, "q"), right=named(20, "d"),
        isNonBlocking=nonblocking,
    ))
    if multi:
        statement = node("List", list=[statement, node(
            "ExpressionStatement", expr=node(
                "Assignment", left=named(31, "r"), right=named(20, "d"),
                isNonBlocking=nonblocking,
            ),
        )])
    return node("ProceduralBlock", procedureKind=procedure, body=node(
        "Timed", timing=timing, stmt=statement,
    ))


def design(kind="direct", **kwargs):
    body = [
        node("Port", name="clk", addr=10, direction="In", type="logic"),
        node("Port", name="d", addr=20, direction="In", type="logic"),
        node("Port", name="q", addr=30, direction="Out", type="logic"),
        node("Port", name="r", addr=31, direction="Out", type="logic"),
        node("Net", name="clk", addr=10, type="logic"),
        node("Net", name="d", addr=20, type="logic"),
        node("Variable", name="q", addr=30, type="logic"),
        node("Variable", name="r", addr=31, type="logic"),
        process(kind, **kwargs),
    ]
    return {"design": node("Root", members=[
        node("Instance", name="top", body=node(
            "InstanceBody", name="top", members=body,
        )),
    ])}


def kinds(graph):
    return {(e["source"], e["target"], e["kind"], e["detail"],
             e["sequential"]) for e in graph["edges"]}


def test_direct_signal_event_adds_real_clock_edge_and_sequential_assignment():
    ast = design("direct", multi=True)
    graph = build_dependency_graph(ast, expected_top="top")
    got = kinds(graph)
    assert ("top.clk", "top.q", "event", "PosEdge", True) in got
    assert ("top.clk", "top.r", "event", "PosEdge", True) in got
    assert ("top.d", "top.q", "data", "", True) in got
    assert ("top.d", "top.r", "data", "", True) in got
    assert not any(e["source"] == "top.d" and e["kind"] == "event"
                   for e in graph["edges"])
    assert graph["counts"]["warnings"] == 0
    expr = build_expression_index(ast, expected_top="top")
    rows = {row["target"]: row for row in expr["items"]}
    assert rows["top.q"]["events"][0]["edge"] == "PosEdge"
    assert rows["top.q"]["events"][0]["expression"]["path"] == "top.clk"
    assert rows["top.q"]["coverage"] == "syntax_supported"


def test_implicit_event_has_data_edges_but_never_invents_event_or_clock():
    ast = design("implicit", nonblocking=False)
    graph = build_dependency_graph(ast, expected_top="top")
    got = kinds(graph)
    assert ("top.d", "top.q", "data", "", False) in got
    assert not any(e["kind"] == "event" for e in graph["edges"])
    assert graph["counts"]["warnings"] == 0
    # Expressions separately document that implicit sensitivity is not
    # a fully captured event expression; no fake "posedge" is exported.
    rows = build_expression_index(ast, expected_top="top")["items"]
    assert len(rows) == 1
    assert rows[0]["events"] == []
    assert rows[0]["coverage"] == "partial"


def test_event_list_keeps_existing_edges_and_resolved_identity():
    graph = build_dependency_graph(design("list"), expected_top="top")
    assert ("top.clk", "top.q", "event", "PosEdge", True) in kinds(graph)
    assert graph["warnings"] == []


@pytest.mark.parametrize("edge", ["NegEdge", "PosEdge"])
def test_both_explicit_polarities_are_kept(edge):
    graph = build_dependency_graph(design("direct", edge=edge), expected_top="top")
    assert ("top.clk", "top.q", "event", edge, True) in kinds(graph)


@pytest.mark.parametrize("edge", ["NoEdge", "BothEdges", "Unknown", None])
def test_unsupported_edge_does_not_make_up_clock_edges(edge):
    ast = design("direct", edge=edge)
    graph = build_dependency_graph(ast, expected_top="top")
    assert not any(e["kind"] == "event" for e in graph["edges"])
    assert any("Front SignalEvent non pris en charge" in w["reason"]
               for w in graph["warnings"])
    assert ("top.d", "top.q", "data", "", False) in kinds(graph)
    rows = build_expression_index(ast, expected_top="top")["items"]
    assert rows[0]["events"] == []
    assert rows[0]["coverage"] == "partial"


def test_unresolvable_clock_same_name_never_binds_wrong_identity():
    graph = build_dependency_graph(
        design("direct", ref_address=999), expected_top="top",
    )
    assert not any(e["kind"] == "event" for e in graph["edges"])
    assert any("sans référence" in w["reason"] for w in graph["warnings"])


@pytest.mark.parametrize("mode", ["broken-list", "empty-list", "unsupported"])
def test_malformed_or_unknown_timing_is_reported(mode):
    graph = build_dependency_graph(design(mode), expected_top="top")
    assert graph["warnings"], mode
    assert not any(e["kind"] == "event" for e in graph["edges"])


def test_always_ff_implicit_sensitivity_is_not_silenced():
    graph = build_dependency_graph(
        design("implicit", procedure="AlwaysFF"), expected_top="top",
    )
    assert any("inattendue" in w["reason"] for w in graph["warnings"])
    assert not any(e["kind"] == "event" for e in graph["edges"])
