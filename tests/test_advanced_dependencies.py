"""Tests unitaires : case, concaténation, indices et generate élaboré."""
from rtlprep.dependencies import build_dependency_graph


def node(kind, **kwargs):
    return {"kind": kind, **kwargs}


def name(symbol, **kwargs):
    return node("NamedValue", symbol=f"123 {symbol}", **kwargs)


def assign(destination, source):
    return node("Assignment", left=name(destination), right=source, isNonBlocking=False)


def statement(destination, source):
    return node("ExpressionStatement", expr=assign(destination, source))


def synthetic_advanced():
    values = ("data_a", "data_b", "sel", "idx", "merged", "picked", "result",
              "mode_result", "dyn_label")
    body = [node("Variable", name=value, type="logic") for value in values]
    body.extend([
        node("ContinuousAssign", assignment=assign("merged",
            node("Concatenation", operands=[
                node("RangeSelect", value=name("data_a"),
                     left=node("BinaryOp", left=name("WIDTH", constant="8"),
                          right=node("IntegerLiteral", value="1"), op="Subtract"),
                     right=node("IntegerLiteral", value="4")),
                node("RangeSelect", value=name("data_b"),
                     left=node("IntegerLiteral", value="3"),
                     right=node("IntegerLiteral", value="0"))
            ]))),
        node("ContinuousAssign", assignment=assign("picked",
            node("ElementSelect", value=name("data_a"), selector=name("idx")))),
        node("ProceduralBlock", procedureKind="AlwaysComb",
             body=node("Block", body=node("Case", condition="Normal",
                 expr=name("sel"), items=[
                     {"expressions": [node("IntegerLiteral", value="0")],
                      "stmt": statement("result", name("merged"))},
                     {"expressions": [name("dyn_label")],
                      "stmt": statement("result", name("data_a"))}
                 ], defaultCase=statement("result", name("data_b"))))),
        node("GenerateBlock", isUninstantiated=False, members=[
            node("ContinuousAssign", assignment=assign("mode_result",
                node("BinaryOp", left=name("data_a"), right=name("data_b"),
                     op="BinaryXor")))
        ]),
        node("GenerateBlock", isUninstantiated=True, members=[
            node("ContinuousAssign", assignment=assign("mode_result",
                name("sel")))
        ]),
    ])
    return {"design": node("Root", members=[
        node("Instance", name="top", body=node("InstanceBody", name="top",
            members=body))
    ])}


def test_advanced_graph_data_control_and_generate():
    graph = build_dependency_graph(synthetic_advanced(), expected_top="top")
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    wanted = {
        ("top.data_a", "top.merged", "data"),
        ("top.data_b", "top.merged", "data"),
        ("top.data_a", "top.picked", "data"),
        ("top.idx", "top.picked", "data"),
        ("top.sel", "top.result", "control"),
        ("top.dyn_label", "top.result", "control"),
        ("top.merged", "top.result", "data"),
        ("top.data_a", "top.result", "data"),
        ("top.data_b", "top.result", "data"),
        ("top.data_a", "top.mode_result", "data"),
        ("top.data_b", "top.mode_result", "data"),
    }
    assert wanted.issubset(edges), sorted(wanted - edges)
    assert ("top.sel", "top.mode_result", "data") not in edges
    assert not any("WIDTH" in str(x) for x in graph["warnings"])
    assert graph["counts"]["warnings"] == 1
    assert "signal entier" in graph["warnings"][0]["reason"]


def test_non_normal_case_reports_warning():
    ast = synthetic_advanced()
    case = ast["design"]["members"][0]["body"]["members"][11]["body"]["body"]
    assert case["kind"] == "Case"
    case["condition"] = "WildcardX"
    graph = build_dependency_graph(ast, expected_top="top")
    assert any("Case à comparaisons spéciales" in w["reason"] for w in graph["warnings"])


def test_malformed_concat_does_not_invent_edges():
    ast = synthetic_advanced()
    concat = ast["design"]["members"][0]["body"]["members"][9]["assignment"]["right"]
    assert concat["kind"] == "Concatenation"
    concat.pop("operands")
    graph = build_dependency_graph(ast, expected_top="top")
    edges = {(x["source"], x["target"], x["kind"]) for x in graph["edges"]}
    assert ("top.data_a", "top.merged", "data") not in edges
    assert any("Concatenation sans liste" in w["reason"] for w in graph["warnings"])
