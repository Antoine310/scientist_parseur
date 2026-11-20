"""Tests sans outil EDA : graphes synthétiques et recherche bornée."""
import json

import pytest

from rtlprep.dependencies import build_dependency_graph, trace_dependencies
from rtlprep.manifest import load_design
from rtlprep import runner


def n(kind, name="", **kwargs):
    return {"kind": kind, "name": name, **kwargs}


def ref(name):
    return {"kind": "NamedValue", "symbol": "123456 " + name}


def assign(name, expr):
    return {"kind": "Assignment", "left": ref(name), "right": expr, "isNonBlocking": False}


def design_ast():
    leaf = n("Instance", "child",
             body=n("InstanceBody", "leaf", members=[
                 n("Port", "a", direction="In", type="logic"),
                 n("Net", "a", type="logic"),
                 n("Port", "y", direction="Out", type="logic"),
                 n("Variable", "y", type="logic"),
                 n("ContinuousAssign", assignment=assign("y", ref("a"))),
             ]),
             connections=[
                 {"port": n("Port", "a", direction="In"), "expr": ref("a")},
                 {"port": n("Port", "y", direction="Out"),
                  "expr": assign("out", n("EmptyArgument"))},
             ])
    proc = n("ProceduralBlock", procedureKind="AlwaysFF",
             body=n("Timed", timing=n("EventList", events=[
                 n("SignalEvent", expr=ref("clk"), edge="PosEdge")]),
                 stmt=n("Conditional", conditions=[{"expr": ref("sel")}],
                     ifTrue=n("ExpressionStatement", expr=assign("count",
                         n("BinaryOp", op="Add", left=ref("count"),
                           right=n("IntegerLiteral", value="1'b1")))))))
    top_members = []
    for name in ("a", "clk", "sel"):
        top_members.extend([n("Port", name, direction="In", type="logic"),
                            n("Net", name, type="logic")])
    for name in ("out", "count"):
        top_members.extend([n("Port", name, direction="Out", type="logic"),
                            n("Variable", name, type="logic")])
    top_members += [leaf, proc]
    return {"design": n("Root", members=[
        n("Instance", "top", body=n("InstanceBody", "top", members=top_members))
    ])}


def edges(graph):
    return {(x["source"], x["target"], x["kind"]) for x in graph["edges"]}


def test_typed_connections_and_sequential_controls():
    graph = build_dependency_graph(design_ast(), expected_top="top")
    required = {
        ("top.a", "top.child.a", "port_input"),
        ("top.child.a", "top.child.y", "data"),
        ("top.child.y", "top.out", "port_output"),
        ("top.sel", "top.count", "control"),
        ("top.clk", "top.count", "event"),
        ("top.count", "top.count", "data"),
    }
    assert required.issubset(edges(graph))
    assert graph["counts"]["warnings"] == 0
    assert {e["detail"] for e in graph["edges"] if e["kind"] == "event"} == {"PosEdge"}
    assert next(e for e in graph["edges"] if e["kind"] == "data"
                and e["target"] == "top.count")["sequential"] is True


def test_bounded_fanin_fanout_and_cycle():
    graph = build_dependency_graph(design_ast(), expected_top="top")
    result = trace_dependencies(graph, "top.out", "fanin", max_depth=4)
    assert "top.a" in result["visited_nodes"]
    assert len(result["edges"]) == 3
    other = trace_dependencies(graph, "top.a", "fanout", max_depth=4)
    assert "top.out" in other["visited_nodes"]
    assert trace_dependencies(graph, "top.count", "fanin", max_depth=8)["truncated"] is False
    assert len(trace_dependencies(graph, "top.out", max_edges=1)["edges"]) == 1
    with pytest.raises(KeyError):
        trace_dependencies(graph, "top.unknown")
    with pytest.raises(ValueError):
        trace_dependencies(graph, "top.a", max_depth=16)


def test_unknown_expression_is_warned_not_guessed():
    ast = design_ast()
    leaf = ast["design"]["members"][0]["body"]["members"][-2]
    leaf["body"]["members"][-1]["assignment"]["right"] = {"kind": "Call"}
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") not in edges(graph)
    assert graph["counts"]["warnings"] >= 1


def test_no_stale_graph_if_compiler_missing(tmp_path, monkeypatch):
    d = load_design("examples/counter/design.json")
    (tmp_path / "rtl_dependencies.json").write_text('{"old": true}')
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    result = runner.dependency_design(d, tmp_path, 1)
    assert result["status"] == "missing_tool"
    assert not (tmp_path / "rtl_dependencies.json").exists()
    assert json.loads((tmp_path / "deps.result.json").read_text())["status"] == "missing_tool"


def test_slang_list_statement_sequence_is_traversed():
    """Regression for real slang v12.1: begin/end is kind=List, field 'list'."""
    ast = design_ast()
    body = ast["design"]["members"][0]["body"]["members"]
    proc = next(x for x in body if x.get("kind") == "ProceduralBlock")
    old_stmt = proc["body"]["stmt"]
    proc["body"]["stmt"] = n("List", list=[
        old_stmt,
        n("ExpressionStatement", expr=assign("out", ref("a"))),
    ])
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.a", "top.out", "data") in edges(graph)
    assert graph["counts"]["warnings"] == 0


def test_invalid_slang_list_is_reported_not_silently_ignored():
    ast = design_ast()
    body = ast["design"]["members"][0]["body"]["members"]
    proc = next(x for x in body if x.get("kind") == "ProceduralBlock")
    proc["body"]["stmt"] = n("List")
    graph = build_dependency_graph(ast, expected_top="top")
    assert any("List sans liste" in x["reason"] for x in graph["warnings"])
