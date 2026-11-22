"""Test vrai client MCP stdio : gardes et événements du compteur compilé."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def run() -> None:
    from mcp import Client, StdioServerParameters

    root = Path("reports/mcp-counter").resolve()
    params = StdioServerParameters(command=sys.executable, args=[
        "-m", "rtlprep", "mcp",
        "--index", str(root / "rtl_index.json"),
        "--graph", str(root / "rtl_dependencies.json"),
        "--manifest", str(Path("examples/counter/design.json").resolve()),
        "--reports-dir", str(root),
    ])
    async with Client(params) as client:
        caps = await client.call_tool("rtl_capabilities", {})
        assert not caps.is_error, caps
        assert caps.structured_content["expressions_available"] is True
        response = await client.call_tool("rtl_expressions", {"signal": "counter.count"})
        assert not response.is_error, response
        payload = response.structured_content
        assert payload["total"] == 2, payload
        assert payload["scope"] == "continuous_and_supported_procedural_assignments"
        assert all(r["assignment_kind"] == "procedural" for r in payload["items"])
        assert all(r["procedure_kind"] == "AlwaysFF" for r in payload["items"])
        assert any(len(r["guards"]) == 2 for r in payload["items"])
        assert all(any(e["edge"] == "PosEdge" for e in r["events"])
                   for r in payload["items"])
        assert payload["source_snapshot_status"] == "matching", payload
        assert caps.structured_content["register_flow_available"] is True
        assert caps.structured_content["bit_accesses_available"] is True
        assert caps.structured_content["coverage_available"] is True
        assert caps.structured_content["sequential_candidates_available"] is True
        assert caps.structured_content["evidence_available"] is True
        flow_response = await client.call_tool(
            "rtl_register_flow", {"signal": "counter.count"}
        )
        assert not flow_response.is_error, flow_response
        flow = flow_response.structured_content
        assert flow["total"] == 1, flow
        process = flow["items"][0]
        assert process["coverage"] == "syntactic_paths_supported", process
        assert process["path_count"] == 3, process
        assert sorted(p["write_count"] for p in process["paths"]) == [0, 1, 1]
        assert process["hold_candidate"] == "syntactic_unwritten_path"
        assert process["same_path_multiple_nba"] is False
        assert flow["source_snapshot_status"] == "matching", flow
        bit_response = await client.call_tool(
            "rtl_bit_accesses", {"signal": "counter.count"}
        )
        assert not bit_response.is_error, bit_response
        bits = bit_response.structured_content
        # Counter uses procedural assignments; this tool only covers continuous assigns.
        assert bits["total"] == 0, bits
        assert bits["source_snapshot_status"] == "matching", bits
        coverage_response = await client.call_tool("rtl_coverage", {})
        assert not coverage_response.is_error, coverage_response
        coverage = coverage_response.structured_content
        assert coverage["design_coverage"] == "not_measured", coverage
        assert coverage["source_snapshot_status"] == "matching", coverage
        assert coverage["analyzers"]["register_flow"]["captured"] >= 1, coverage
        seq_response = await client.call_tool(
            "rtl_sequential_candidates", {"signal": "counter.count"}
        )
        assert not seq_response.is_error, seq_response
        seq = seq_response.structured_content
        assert seq["total"] == 1, seq
        row = seq["items"][0]
        assert row["coverage"] == "syntactic_candidates_supported", row
        assert len(row["paths"]) == 3, row
        assert row["reset_like_detection"] == "candidate_found", row
        assert any(
            path["reset_like_guard_candidate"] is not None
            and path["reset_like_guard_candidate"]["signal"] == "counter.rst_n"
            and path["reset_like_guard_candidate"]["edge"] == "NegEdge"
            for path in row["paths"]
        ), row
        assert seq["source_snapshot_status"] == "matching", seq
        evidence_response = await client.call_tool(
            "rtl_evidence", {"signal": "counter.count"}
        )
        assert not evidence_response.is_error, evidence_response
        evidence = evidence_response.structured_content
        assert evidence["total"] == 3, evidence
        assert evidence["source_snapshot_status"] == "matching", evidence
        assert len(evidence["rtl_anchors"]) >= 1, evidence
        assert all(item["usable_for_current_snapshot"] is False
                   for item in evidence["items"]), evidence
        print("MCP_PROCEDURAL_STDIO_PASSED", payload["total"], flow["total"])


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run(), timeout=45))
