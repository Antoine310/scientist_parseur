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
        print("MCP_PROCEDURAL_STDIO_PASSED", payload["total"])


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run(), timeout=45))
