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


def test_real_slang_replication_count_and_concat_are_traversed():
    """slang exports {6{a}} as Replication(count, concat), not 'operands'."""
    ast = design_ast()
    body = ast["design"]["members"][0]["body"]["members"]
    child = next(x for x in body if x.get("kind") == "Instance")
    continuous = next(x for x in child["body"]["members"]
                      if x.get("kind") == "ContinuousAssign")
    continuous["assignment"]["right"] = n(
        "Replication",
        count=n("IntegerLiteral", value="6"),
        concat=n("Concatenation", operands=[ref("a")]),
    )
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") in edges(graph)
    assert graph["counts"]["warnings"] == 0


def test_malformed_replication_is_reported():
    ast = design_ast()
    child = next(x for x in ast["design"]["members"][0]["body"]["members"]
                 if x.get("kind") == "Instance")
    assign_stmt = next(x for x in child["body"]["members"]
                       if x.get("kind") == "ContinuousAssign")
    assign_stmt["assignment"]["right"] = n("Replication", count=n("IntegerLiteral", value="6"))
    graph = build_dependency_graph(ast, expected_top="top")
    assert any("Replication sans concaténation" in x["reason"] for x in graph["warnings"])



def test_semantic_parameter_references_from_package_not_counted_as_signals():
    """Use actual declaration IDs: OPCODE names are not a special-case rule."""
    ast = design_ast()
    package = n("Package", "pkg", members=[
        n("Parameter", "constant_value", addr="700", value="7'h13"),
        n("Parameter", "a", addr="701", value="1"),
    ])
    ast["design"]["members"].insert(0, n("CompilationUnit", members=[package]))
    child = next(x for x in ast["design"]["members"][1]["body"]["members"]
                 if x.get("kind") == "Instance")
    assign_stmt = next(x for x in child["body"]["members"]
                       if x.get("kind") == "ContinuousAssign")
    assign_stmt["assignment"]["right"] = n("BinaryOp", op="BinaryOr",
        left=ref("a"), right=n("NamedValue", symbol="700 constant_value"))
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") in edges(graph)
    assert graph["counts"]["warnings"] == 0
    assert graph["resolved_parameter_symbols"] == ["constant_value"]

    # A local signal and an imported parameter with the SAME NAME should not
    # be confused: the compiler's semantic symbol ID is decisive.
    assign_stmt["assignment"]["right"] = n("NamedValue", symbol="701 a")
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") not in edges(graph)
    assert graph["counts"]["warnings"] == 0
    assert graph["resolved_parameter_symbols"] == ["a"]


def test_unresolved_symbol_still_warns_instead_of_using_name_prefix():
    ast = design_ast()
    child = next(x for x in ast["design"]["members"][0]["body"]["members"]
                 if x.get("kind") == "Instance")
    stmt = next(x for x in child["body"]["members"]
                if x.get("kind") == "ContinuousAssign")
    stmt["assignment"]["right"] = n("NamedValue", symbol="500 OPCODE_UNKNOWN")
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") not in edges(graph)
    assert any("OPCODE_UNKNOWN" in x["reason"] for x in graph["warnings"])



def test_enum_values_resolve_through_compiler_id_not_name():
    """ALU opcodes are EnumValue declarations, not ordinary parameters."""
    ast = design_ast()
    enum = n("EnumType", "alu_opcode_e", members=[
        n("EnumValue", "ALU_ADD", addr=900, value="7'b0011000"),
        n("EnumValue", "a", addr=901, value="7'b0011001"),
    ])
    ast["design"]["members"].insert(0, n("CompilationUnit", members=[
        n("Package", "pkg", members=[enum])
    ]))
    leaf = next(m for m in ast["design"]["members"][1]["body"]["members"]
                if m.get("kind") == "Instance")
    assign_stmt = next(m for m in leaf["body"]["members"]
                       if m.get("kind") == "ContinuousAssign")

    assign_stmt["assignment"]["right"] = n(
        "BinaryOp", op="BinaryOr",
        left=ref("a"), right=n("NamedValue", symbol="900 ALU_ADD"))
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") in edges(graph)
    assert graph["counts"]["warnings"] == 0
    assert graph["resolved_enum_symbols"] == ["ALU_ADD"]

    # Even when an enum item shares a name with a signal in the instance,
    # the enum reference's exact ID must suppress a fake signal dependency.
    assign_stmt["assignment"]["right"] = n("NamedValue", symbol="901 a")
    graph = build_dependency_graph(ast, expected_top="top")
    assert ("top.child.a", "top.child.y", "data") not in edges(graph)
    assert graph["resolved_enum_symbols"] == ["a"]
    assert graph["counts"]["warnings"] == 0
