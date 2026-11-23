"""PR29: identités AST dans les generate actifs, sans fusion d'homonymes."""
from __future__ import annotations

import pytest

from rtlprep.dependencies import build_dependency_graph, trace_dependencies
from rtlprep.expressions import build_expression_index
from rtlprep.index import build_index, get_signal_info


def n(kind, **fields):
    return {"kind": kind, **fields}


def named(addr, name):
    return n("NamedValue", symbol=f"{addr} {name}")


def assignment(dst_addr, dst_name, src_addr, src_name):
    return n("ContinuousAssign", assignment=n(
        "Assignment", left=named(dst_addr, dst_name),
        right=named(src_addr, src_name), isNonBlocking=False,
    ))


def source():
    body = [
        n("Net", name="tmp", addr=10, type="logic"),
        n("Net", name="out_a", addr=100, type="logic"),
        n("Net", name="out_b", addr=101, type="logic"),
        n("Net", name="out_bad", addr=102, type="logic"),
        n("GenerateBlock", name="first", isUninstantiated=False, members=[
            n("Variable", name="tmp", addr=20, type="logic",
              source_file="top.sv", source_line=6, source_column=3),
            assignment(100, "out_a", 20, "tmp"),
            # Reference to a different, same-named declaration at top level.
            assignment(20, "tmp", 10, "tmp"),
        ]),
        n("GenerateBlock", name="second", isUninstantiated=False, members=[
            n("Variable", name="tmp", addr=30, type="logic"),
            assignment(101, "out_b", 30, "tmp"),
            assignment(30, "tmp", 20, "tmp"),
        ]),
        n("GenerateBlock", name="ignored", isUninstantiated=True, members=[
            n("Variable", name="tmp", addr=40, type="logic"),
            assignment(102, "out_bad", 40, "tmp"),
        ]),
        assignment(102, "out_bad", 999, "tmp"),
    ]
    return {"design": n("Root", members=[
        n("Instance", name="top", body=n(
            "InstanceBody", name="top", members=body,
        )),
    ])}


def test_index_qualifies_active_scopes_and_skips_inactive_branch():
    idx = build_index(source(), expected_top="top")
    paths = {row.get("path") or f"{row['instance_path']}.{row['name']}"
             for row in idx["signals"]}
    assert {"top.tmp", "top.first.tmp", "top.second.tmp", "top.out_a"} <= paths
    assert "top.ignored.tmp" not in paths
    rows = get_signal_info(idx, "top", "first.tmp")["declarations"]
    assert rows[0]["scope"] == "first"
    assert rows[0]["source"]["line"] == 6
    with pytest.raises(KeyError):
        get_signal_info(idx, "top", "ignored.tmp")
    with pytest.raises(KeyError):
        get_signal_info(idx, "top", "fake.tmp")


def test_graph_uses_exact_identity_even_when_names_collide():
    ast = source()
    idx = build_index(ast, expected_top="top")
    graph = build_dependency_graph(ast, expected_top="top", index=idx)
    edges = {(x["source"], x["target"], x["kind"]) for x in graph["edges"]}
    assert ("top.first.tmp", "top.out_a", "data") in edges
    assert ("top.second.tmp", "top.out_b", "data") in edges
    assert ("top.tmp", "top.first.tmp", "data") in edges
    assert ("top.first.tmp", "top.second.tmp", "data") in edges
    assert ("top.tmp", "top.out_a", "data") not in edges
    assert ("top.second.tmp", "top.out_a", "data") not in edges
    assert ("top.tmp", "top.out_bad", "data") not in edges
    assert ("top.ignored.tmp", "top.out_bad", "data") not in edges
    assert any("inconnue/ambiguë" in w["reason"] for w in graph["warnings"])
    assert {"top.first.tmp", "top.tmp"} <= set(trace_dependencies(
        graph, "top.out_b", "fanin", max_depth=4,
    )["visited_nodes"])


def test_expressions_use_same_identity_not_flat_name():
    ast = source()
    idx = build_index(ast, expected_top="top")
    exprs = build_expression_index(ast, expected_top="top", index=idx)
    items = {row["target"]: row for row in exprs["items"]}
    assert items["top.out_a"]["expression"] == {
        "kind": "signal", "name": "tmp", "path": "top.first.tmp"
    }
    assert items["top.out_b"]["expression"]["path"] == "top.second.tmp"
    assert "top.out_bad" not in items or (
        items["top.out_bad"]["expression"]["kind"] == "unsupported"
    )


def test_unknown_identity_never_binds_known_name():
    ast = source()
    ast["design"]["members"][0]["body"]["members"][-1] = (
        assignment(102, "out_bad", 300, "tmp")
    )
    graph = build_dependency_graph(ast, expected_top="top")
    assert not any(e["target"] == "top.out_bad" for e in graph["edges"])
    assert any("tmp" in w["reason"] for w in graph["warnings"])


def test_malformed_generate_name_not_flattened_into_module_scope():
    ast = source()
    block = ast["design"]["members"][0]["body"]["members"][4]
    block["name"] = ""
    idx = build_index(ast, expected_top="top")
    assert not any(row.get("path") == "top.first.tmp"
                   for row in idx["signals"])
    graph = build_dependency_graph(ast, expected_top="top", index=idx)
    assert not any(e["source"] == "top.tmp" and e["target"] == "top.out_a"
                   for e in graph["edges"])


def test_same_symbol_address_only_resolves_inside_matching_instance():
    body = [n("Net", name="a", addr=50, type="logic"),
            n("Net", name="b", addr=51, type="logic"),
            assignment(51, "b", 50, "a")]
    ast = {"design": n("Root", members=[
        n("Instance", name="left", body=n("InstanceBody", name="leaf", members=body)),
        n("Instance", name="right", body=n("InstanceBody", name="leaf", members=body)),
    ])}
    graph = build_dependency_graph(ast, expected_top="left")
    edges = {(e["source"], e["target"]) for e in graph["edges"]}
    assert edges == {("left.a", "left.b"), ("right.a", "right.b")}
