"""PR #33: static selection evidence and constant-only initial metadata."""
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
PINNED = (
    ("priority_encoder", ROOT / "upstream_unknown/verilog-axis/rtl/priority_encoder.v",
     "cf82512ba84c43cfddc7728782493241b563b8f3"),
    ("rxuart", ROOT / "upstream_unknown/wbuart32/rtl/rxuart.v",
     "1506e563944a2da1c1b01be6c1a953ad92fdff7d"),
)


def n(kind, **kwargs):
    return {"kind": kind, **kwargs}


def ref(name, addr="123", **kwargs):
    return n("NamedValue", symbol=f"{addr} {name}", **kwargs)


def literal(value):
    return n("IntegerLiteral", value=value)


def assignment(lhs, rhs):
    return n("Assignment", left=lhs, right=rhs, isNonBlocking=False)


def stmt(lhs, rhs):
    return n("ExpressionStatement", expr=assignment(lhs, rhs))


def synthetic(*items):
    names = ("data", "out", "idx", "init")
    declarations = [n("Variable", name=name, type="logic") for name in names]
    return {"design": n("Root", members=[
        n("Instance", name="top", body=n(
            "InstanceBody", name="top", members=declarations + list(items),
        )),
    ])}


def graph(*items):
    return build_dependency_graph(synthetic(*items), expected_top="top")


def links(value, kind):
    return {(e["source"], e["target"]) for e in value["edges"] if e["kind"] == kind}


def initial(body):
    return n("ProceduralBlock", procedureKind="Initial", body=body)


def test_static_rhs_and_lhs_positions_are_recorded_not_conflated_with_bit_edges():
    lhs = n("RangeSelect", value=ref("out"),
            left=literal("5"), right=literal("2"))
    rhs = n("RangeSelect", value=ref("data"),
            left=literal("7"), right=literal("4"))
    g = graph(n("ContinuousAssign", assignment=assignment(lhs, rhs)))
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert links(g, "data") == {("top.data", "top.out")}
    assert {(x["role"], x["signal"], x["selection"]["kind"])
            for x in g["static_selections"]} == {
                ("read", "top.data", "range"), ("write", "top.out", "range"),
            }
    assert g["static_selections"][0]["selection"] in (
        {"kind": "range", "msb": 7, "lsb": 4},
        {"kind": "range", "msb": 5, "lsb": 2},
    )
    assert "sans granularité bit" in g["limitations"][0]


def test_static_bit_to_bit_selection_is_explicit_evidence():
    lhs = n("ElementSelect", value=ref("out"), selector=literal("2"))
    rhs = n("ElementSelect", value=ref("data"), selector=literal("5"))
    g = graph(n("ContinuousAssign", assignment=assignment(lhs, rhs)))
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert {x["selection"]["index"] for x in g["static_selections"]} == {2, 5}
    assert links(g, "data") == {("top.data", "top.out")}


def test_dynamic_selector_stays_reported_and_remains_data_source():
    rhs = n("ElementSelect", value=ref("data"), selector=ref("idx"))
    g = graph(n("ContinuousAssign", assignment=assignment(ref("out"), rhs)))
    assert links(g, "data") == {
        ("top.data", "top.out"), ("top.idx", "top.out"),
    }
    assert not g["static_selections"]
    assert any("signal entier" in w["reason"] for w in g["warnings"])


def test_elaborated_constant_index_is_recorded_without_fake_constant_signal():
    rhs = n("ElementSelect", value=ref("data"), selector=n(
        "BinaryOp", op="Subtract",
        left=ref("WIDTH", "721", constant="8"), right=literal("1"),
    ))
    g = graph(n("ContinuousAssign", assignment=assignment(ref("out"), rhs)))
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert g["static_selections"][0]["selection"] == {"kind": "bit", "index": 7}
    assert links(g, "data") == {("top.data", "top.out")}


def test_slang_folded_multiply_index_and_nested_selection():
    # A generate variable 'n' is an elaboration constant, not a runtime net.
    generated = n("BinaryOp", op="Multiply",
                  left=ref("gen_n", "721", constant="2"),
                  right=literal("2"), constant="4")
    nested = n("ElementSelect",
               value=n("ElementSelect",
                       value=ref("data"), selector=literal("0")),
               selector=generated)
    g = graph(n("ContinuousAssign", assignment=assignment(ref("out"), nested)))
    assert g["counts"]["warnings"] == 0, g["warnings"]
    assert links(g, "data") == {("top.data", "top.out")}
    assert any(
        entry["selection"] == {
            "kind": "nested", "parts": [
                {"kind": "bit", "index": 0},
                {"kind": "bit", "index": 4},
            ],
        }
        for entry in g["static_selections"]
    )


def test_folded_constant_on_runtime_signal_is_not_static_index():
    selector = n("BinaryOp", op="Add", left=ref("idx", constant="1"),
                 right=literal("1"), constant="2")
    g = graph(n("ContinuousAssign", assignment=assignment(
        ref("out"), n("ElementSelect", value=ref("data"), selector=selector)
    )))
    assert not g["static_selections"]
    assert any("signal entier" in w["reason"] for w in g["warnings"])
    assert ("top.idx", "top.out") in links(g, "data")


def test_constant_initial_is_metadata_only_not_runtime_dependency():
    g = graph(initial(stmt(ref("init"), literal("1'b0"))))
    assert g["edges"] == []
    assert g["counts"]["warnings"] == 0
    assert len(g["initializations"]) == 1
    assert g["initializations"][0]["target"] == "top.init"
    assert g["initializations"][0]["scope"] == "initial_only_not_runtime"


def test_semantic_parameter_slice_is_a_safe_initializer_not_a_runtime_read():
    tree = synthetic(initial(stmt(ref("init"), n("RangeSelect",
        value=ref("RESET_VALUE", "777"),
        left=literal("7"), right=literal("0")))))
    tree["design"]["members"].insert(0, n("CompilationUnit", members=[
        n("Package", name="pkg", members=[
            n("Parameter", name="RESET_VALUE", addr="777", value="8'h00")
        ])
    ]))
    g = build_dependency_graph(tree, expected_top="top")
    assert not g["edges"]
    assert len(g["initializations"]) == 1
    assert g["counts"]["warnings"] == 0, g["warnings"]


def test_initial_runtime_signal_read_is_rejected_without_fake_edges():
    g = graph(initial(stmt(ref("init"), ref("data"))))
    assert g["initializations"] == []
    assert g["edges"] == []
    assert any("Initial" in w["reason"] for w in g["warnings"])


def test_constant_tag_on_runtime_signal_is_not_initializer_proof():
    g = graph(initial(stmt(ref("init"), ref("data", constant="1'b0"))))
    assert not g["initializations"]
    assert any("Initial" in w["reason"] for w in g["warnings"])


def test_mixed_supported_unsupported_initial_block_is_atomic():
    body = n("List", list=[
        stmt(ref("init"), literal("0")),
        stmt(ref("out"), ref("data")),
    ])
    g = graph(initial(body))
    assert g["initializations"] == []
    assert g["edges"] == []
    assert any("Initial" in w["reason"] for w in g["warnings"])


def test_initial_unknown_destination_and_unsupported_statement_stay_reported():
    for body in (stmt(ref("not_declared"), literal("0")),
                 n("Timed", timing=n("SignalEvent", edge="PosEdge", expr=ref("data")))):
        g = graph(initial(body))
        assert g["initializations"] == []
        assert not g["edges"]
        assert g["counts"]["warnings"] > 0


@pytest.mark.parametrize("top,source,pin", PINNED)
@pytest.mark.skipif(shutil.which("slang") is None, reason="slang réel absent")
def test_pinned_real_rtl_static_selection_and_initial_metadata(tmp_path, top, source, pin):
    if not source.is_file():
        pytest.skip("checkout RTL épinglé absent")
    assert git_blob_sha1(source.read_bytes()) == pin
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": top, "sources": [str(source)], "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "analysis"
    result = dependency_design(load_design(manifest), out, 90)
    assert result["status"] == "passed", result
    g = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
    assert g["static_selections"], (top, g["warnings"])
    assert all(x["role"] in ("read", "write") for x in g["static_selections"])
    assert g["counts"]["warnings"] == 0, g["warnings"]
    if top == "priority_encoder":
        assert not g["initializations"]
    if top == "rxuart":
        assert len(g["initializations"]) >= 1, g["warnings"]
        assert not any(
            "Procédure non prise en charge : Initial" in w["reason"]
            for w in g["warnings"]
        ), g["warnings"]
