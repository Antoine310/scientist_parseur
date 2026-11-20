"""Reproduce a real CV32E40P compressed-decoder RTLPrep experiment.

Fetch the pinned upstream files separately, then run:
python scripts/run_cv32e40p_decoder.py --source-root /path/to/upstream --out reports/cv32e40p
No LLM, secret, paid API, or local RTL vendor copy required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from rtlprep.dependencies import trace_dependencies
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design

UPSTREAM_REPOSITORY = "openhwfoundation/cv32e40p"
UPSTREAM_COMMIT = "b353438ff469c030c89f6804f3b24a2852880e8b"
TOP = "cv32e40p_compressed_decoder"
REQUIRED_PORTS = {"instr_i", "instr_o", "is_compressed_o", "illegal_instr_o"}


def run_experiment(source_root: Path, out: Path, timeout: int = 180) -> dict:
    """Use genuine upstream RTL and preserve both findings and limitations."""
    source_root = source_root.expanduser().resolve()
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    # Explicit order: the imported SystemVerilog package must precede its user.
    sources = [
        source_root / "rtl/include/cv32e40p_pkg.sv",
        source_root / "rtl/cv32e40p_compressed_decoder.sv",
    ]
    for src in sources:
        if not src.is_file():
            raise FileNotFoundError(f"CV32E40P source missing: {src}")

    manifest = out / "cv32e40p_design.json"
    manifest.write_text(json.dumps({
        "top": TOP, "sources": [str(p) for p in sources],
        "include_dirs": [str(source_root / "rtl/include")],
        "defines": [],
    }, indent=2), encoding="utf-8")

    design = load_design(manifest)
    result = dependency_design(design, out, timeout=timeout)
    if result["status"] != "passed":
        raise RuntimeError(
            f"slang/RTLPrep failed: status={result['status']}; "
            f"details={result.get('error', 'see analyze.result.json and deps.result.json')}"
        )

    index = json.loads((out / "rtl_index.json").read_text(encoding="utf-8"))
    graph = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
    top_instance = next(
        (x for x in index["instances"] if x["path"] == TOP), None
    )
    if top_instance is None:
        raise AssertionError(f"Index missing top instance {TOP}")
    ports = {p["name"]: p["direction"] for p in top_instance["ports"]}
    if not REQUIRED_PORTS <= ports.keys():
        raise AssertionError(f"Missing expected CV32E40P decoder ports: {REQUIRED_PORTS - ports.keys()}")
    if ports["instr_i"] != "In" or any(
        ports[p] != "Out" for p in REQUIRED_PORTS - {"instr_i"}
    ):
        raise AssertionError(f"Unexpected port directions: {ports}")
    if graph["top"] != TOP or not graph["nodes"] or not graph["edges"]:
        raise AssertionError("Dependency graph is empty or refers to the wrong top")

    # Asking for each real output is a useful first CPU-submodule workload.
    fanin = {
        name: trace_dependencies(
            graph, f"{TOP}.{name}", direction="fanin",
            max_depth=10, max_edges=2500,
        ) for name in sorted(REQUIRED_PORTS - {"instr_i"})
    }
    edge_counts = dict(sorted(Counter(edge["kind"] for edge in graph["edges"]).items()))
    # Prevent a false green build when the compiler succeeds but the graph
    # silently loses the input-to-output paths (as happened with AST kind=List).
    disconnected = [
        name for name, response in fanin.items()
        if f"{TOP}.instr_i" not in response["visited_nodes"] or response["truncated"]
    ]
    if disconnected:
        raise AssertionError(
            f"Missing expected CV32E40P decoder input dependencies: {disconnected}"
        )
    test_report = {
        "project": "OpenHW CV32E40P",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_commit": UPSTREAM_COMMIT,
        "top": TOP,
        "sources": [
            {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sources
        ],
        "tools": {
            "slang": subprocess.run(
                ["slang", "--version"], capture_output=True, text=True, check=True
            ).stdout.strip(),
        },
        "status": result["status"],
        "dependency_coverage": "partial" if graph["warnings"] else "within_supported_scope",
        "index_counts": index["counts"],
        "graph_counts": graph["counts"],
        "edge_types": edge_counts,
        "ports": ports,
        "fanin_outputs": {
            name: {
                "reachable_signals": len(response["visited_nodes"]),
                "reachable_from_instr_i": f"{TOP}.instr_i" in response["visited_nodes"],
                "truncated": response["truncated"],
            } for name, response in fanin.items()
        },
        "warnings": graph["warnings"],
        "limitations": graph.get("limitations", []),
        "interpretation": (
            "A successful analysis means compilation/indexing succeeded, NOT "
            "that all RTL semantics or dependencies are understood. Inspect warnings."
        ),
    }
    (out / "cv32e40p_test_report.json").write_text(
        json.dumps(test_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary = {key: value for key, value in test_report.items() if key != "warnings"}
    summary["warning_examples"] = test_report["warnings"][:12]
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return test_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True,
                        help="root of locally downloaded OpenHW CV32E40P source tree")
    parser.add_argument("--out", type=Path, default=Path("reports/cv32e40p"))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run_experiment(args.source_root, args.out, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
