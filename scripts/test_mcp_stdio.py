"""Test d'intégration du VRAI protocole MCP stdio avec le client SDK v2.

Un serveur local est lancé comme sous-processus ; le test appelle réellement
tools/list et tools/call. Les rapports/RTL sont préparés par slang dans la CI.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path



async def run(index: Path, graph: Path, manifest: Path, reports: Path) -> None:
    # Import tardif : pytest -q peut collecter ce script sans l'extra MCP.
    from mcp import Client, StdioServerParameters

    argv = [
        "-m", "rtlprep", "mcp",
        "--index", str(index.resolve()),
        "--graph", str(graph.resolve()),
        "--manifest", str(manifest.resolve()),
        "--reports-dir", str(reports.resolve()),
    ]
    # stdio client : exécute le même serveur que Codex, pas des mocks.
    params = StdioServerParameters(command=sys.executable, args=argv)
    async with Client(params) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        required = {
            "rtl_capabilities", "rtl_modules", "rtl_instances",
            "rtl_module", "rtl_instance", "rtl_signal", "rtl_find_signals",
            "rtl_trace",
            "rtl_warnings", "rtl_source", "rtl_validations",
        }
        assert names == required, (names, required)
        assert not any(
            "run" in x or "execute" in x or "write" in x or "delete" in x
            for x in names
        ), names

        async def call(tool_name: str, **kwargs):
            res = await client.call_tool(tool_name, kwargs)
            assert not res.is_error, (tool_name, res)
            assert isinstance(res.structured_content, dict), (tool_name, res)
            return res.structured_content

        caps = await call("rtl_capabilities")
        assert caps["mode"] == "read_only_snapshot"
        assert caps["runs_eda"] is False and caps["edits_files"] is False
        assert caps["top"] == "hierarchy_top"

        modules = await call("rtl_modules", limit=10)
        assert set(modules["items"]) == {"leaf", "hierarchy_top"}, modules
        tree = await call("rtl_instances", limit=2)
        assert tree["total"] == 3 and tree["next_offset"] == 2, tree
        tail = await call("rtl_instances", limit=2, offset=2)
        assert len(tail["items"]) == 1 and tail["next_offset"] is None
        module = await call("rtl_module", name="leaf")
        assert module["instances"]["total"] == 2
        instance = await call("rtl_instance", path="hierarchy_top.first")
        assert instance["module"] == "leaf"
        signal = await call("rtl_signal", instance_path="hierarchy_top.first",
                            name="status")
        assert signal["instance_path"] == "hierarchy_top.first"
        found = await call("rtl_find_signals", query="status", limit=10)
        assert found["total"] >= 1 and all(
            "status" in item["name"].lower() for item in found["items"]
        ), found
        trace = await call("rtl_trace", signal="hierarchy_top.status",
                           direction="fanin", depth=3, max_edges=20)
        assert trace["edges"], trace
        assert trace["coverage"] in ("partial", "within_supported_scope")
        warnings = await call("rtl_warnings", limit=5)
        assert "total" in warnings
        source = await call("rtl_source", filename="leaf.sv", line=2, radius=1)
        assert source["selected_line"] == 2 and len(source["lines"]) == 3
        reports_list = await call("rtl_validations")
        assert any(x["file"] == "deps.result.json" for x in reports_list["items"])
        assert all(x["origin"] == "stored_report_not_reexecuted"
                   for x in reports_list["items"])

        # Path traversal and unbounded result requests must fail.
        for tool, arguments in [
            ("rtl_source", {"filename": "../.git/config", "line": 1}),
            ("rtl_source", {"filename": "leaf.sv", "line": 1, "radius": 50}),
            ("rtl_trace", {"signal": "hierarchy_top.status", "depth": 12}),
            ("rtl_modules", {"limit": 100000}),
        ]:
            result = await client.call_tool(tool, arguments)
            assert result.is_error, (tool, result)

        print("MCP_STDIO_REAL_PROTOCOL_PASSED", sorted(names),
              "top=", caps["top"], "trace_edges=", len(trace["edges"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(
        run(args.index, args.graph, args.manifest, args.reports_dir),
        timeout=45,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
