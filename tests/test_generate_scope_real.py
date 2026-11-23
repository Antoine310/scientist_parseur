"""Régression contre la véritable IP AXI-Stream épinglée, trois variantes generate."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.field_validation import git_blob_sha1
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream_unknown/verilog-axis/rtl/axis_register.v"
PIN = "93fe0bee6ff1f50d1e2236f5babc283bada2f1a2"

pytestmark = [
    pytest.mark.skipif(shutil.which("slang") is None, reason="slang réel absent"),
    pytest.mark.skipif(not UPSTREAM.is_file(), reason="checkout officiel AXI absent"),
]


@pytest.mark.parametrize("variant", [0, 1, 2])
def test_real_axis_register_generate_scope_and_edges(tmp_path, variant):
    """La compilation du RTL tiers est réelle ; la source officielle est inchangée."""
    assert git_blob_sha1(UPSTREAM.read_bytes()) == PIN
    top = f"axis_variant_{variant}"
    wrapper = tmp_path / "wrapper.sv"
    # Slang treats unconnected output ports as diagnostics with nonzero
    # status. Connect the real module ports explicitly instead of stubbing
    # or suppressing compiler diagnostics.
    inputs = {
        "clk": 1, "rst": 1,
        "s_axis_tdata": 8, "s_axis_tkeep": 1,
        "s_axis_tvalid": 1, "s_axis_tlast": 1,
        "s_axis_tid": 8, "s_axis_tdest": 8, "s_axis_tuser": 1,
        "m_axis_tready": 1,
    }
    outputs = {
        "s_axis_tready": 1,
        "m_axis_tdata": 8, "m_axis_tkeep": 1,
        "m_axis_tvalid": 1, "m_axis_tlast": 1,
        "m_axis_tid": 8, "m_axis_tdest": 8, "m_axis_tuser": 1,
    }
    declarations = [
        f"  logic [{width-1}:0] {name};" if width > 1
        else f"  logic {name};"
        for name, width in (inputs | outputs).items()
    ]
    connections = ",\n".join(
        f"    .{name}({name})" for name in (inputs | outputs)
    )
    wrapper.write_text(
        "`timescale 1ns / 1ps\n" +
        f"module {top};\n" + "\n".join(declarations) + "\n" +
        f"  axis_register #(.REG_TYPE({variant})) dut (\n" +
        connections + "\n  );\nendmodule\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": top,
        "sources": [str(UPSTREAM), str(wrapper)],
        "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "reports"
    result = dependency_design(load_design(manifest), out, 90)
    assert result["status"] == "passed", (
        result,
        (out / "analyze.stderr.log").read_text(encoding="utf-8")
        if (out / "analyze.stderr.log").exists() else "no stderr log",
    )
    idx = json.loads((out / "rtl_index.json").read_text())
    graph = json.loads((out / "rtl_dependencies.json").read_text())
    assert idx["source_fingerprint"] == graph["source_fingerprint"]
    assert idx["top"] == graph["top"] == top
    assert graph["counts"]["edges"] > 0, graph["warnings"]
    instance = f"{top}.dut"
    links = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    scope_nodes = {s["path"] for s in idx["signals"] if s.get("scope")}
    if variant == 0:
        assert not any("temp_m_axis_" in node for node in scope_nodes)
        assert (f"{instance}.s_axis_tdata", f"{instance}.m_axis_tdata", "data") in links
    else:
        local = f"{instance}.genblk1.m_axis_tdata_reg"
        assert local in scope_nodes
        assert (local, f"{instance}.m_axis_tdata", "data") in links
        assert not any(
            "NamedValue inconnue/ambiguë" in w["reason"] and "m_axis_tdata_reg" in w["reason"]
            for w in graph["warnings"]
        ), graph["warnings"]
        if variant == 1:
            assert not any("temp_m_axis_" in node for node in scope_nodes)
        else:
            assert f"{instance}.genblk1.s_axis_tready_early" in scope_nodes
            assert len([n for n in scope_nodes if n.startswith(f"{instance}.genblk1.")]) >= 21
