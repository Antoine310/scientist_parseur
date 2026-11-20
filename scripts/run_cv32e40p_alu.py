"""Reproducible RTLPrep smoke test against genuine OpenHW CV32E40P ALU RTL.

Run after checking out upstream commit pinned in this script:
python scripts/run_cv32e40p_alu.py --source-root upstream_cv32e40p --out reports/alu
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
from run_cv32e40p_decoder import UPSTREAM_COMMIT, UPSTREAM_REPOSITORY, git_blob_hash

TOP = "cv32e40p_alu"
PINNED_BLOBS = {
    "rtl/include/cv32e40p_pkg.sv": "319e790b62623d5daa0388cc92af1ce83aed61fc",
    "rtl/cv32e40p_popcnt.sv": "c7fe53e810c411a4cef0ab6ae8591b9e54e652f9",
    "rtl/cv32e40p_ff_one.sv": "57461c6114763836df894bd5da4c785d727d5afc",
    "rtl/cv32e40p_alu_div.sv": "a7449e01cf1c566838d6e3478c83f34cf66fe892",
    "rtl/cv32e40p_alu.sv": "aa900a787d985d9d62d55118914f2646e4ffc6e5",
}
REQUIRED_INPUTS = {"clk", "rst_n", "operator_i", "operand_a_i", "operand_b_i"}
REQUIRED_OUTPUTS = {"result_o", "comparison_result_o", "ready_o"}


def run_experiment(source_root: Path, out: Path, timeout: int = 180) -> dict:
    source_root = source_root.expanduser().resolve()
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    sources = [source_root / relative for relative in PINNED_BLOBS]
    for relative, expected in PINNED_BLOBS.items():
        path = source_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Upstream source missing: {path}")
        actual = git_blob_hash(path.read_bytes())
        if actual != expected:
            raise ValueError(f"Unexpected CV32E40P source blob {relative}: {actual} != {expected}")

    manifest = out / "cv32e40p_alu_design.json"
    manifest.write_text(json.dumps({
        "top": TOP,
        "sources": [str(p) for p in sources],
        "include_dirs": [str(source_root / "rtl/include")],
        "defines": [],
    }, indent=2), encoding="utf-8")

    result = dependency_design(load_design(manifest), out, timeout=timeout)
    if result["status"] != "passed":
        raise RuntimeError(f"CV32E40P ALU analysis failed: {result}")

    index = json.loads((out / "rtl_index.json").read_text(encoding="utf-8"))
    graph = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
    top_instance = next((inst for inst in index["instances"] if inst["path"] == TOP), None)
    if top_instance is None:
        raise AssertionError("CV32E40P ALU top missing from structural index")
    ports = {port["name"]: port["direction"] for port in top_instance["ports"]}
    if any(ports.get(k) != "In" for k in REQUIRED_INPUTS):
        raise AssertionError(f"CV32E40P ALU input ports missing or wrong: {ports}")
    if any(ports.get(k) != "Out" for k in REQUIRED_OUTPUTS):
        raise AssertionError(f"CV32E40P ALU output ports missing or wrong: {ports}")
    if graph.get("top") != TOP or not graph.get("edges"):
        raise AssertionError("CV32E40P ALU graph missing or empty")
    if index["counts"]["modules"] != 4 or index["counts"]["instances"] != 4:
        raise AssertionError(f"CV32E40P ALU submodule hierarchy incomplete: {index['counts']}")
    if graph["counts"]["edges"] < 300:
        raise AssertionError(f"Suspiciously incomplete ALU dependencies: {graph['counts']}")
    unresolved = [w for w in graph["warnings"]
                  if "Référence NamedValue inconnue" in w["reason"]]
    if unresolved:
        raise AssertionError(f"ALU enum/parameter symbols not resolved: {unresolved[:5]}")

    # Bounded traces on genuine ALU outputs; do not infer semantic correctness
    # from the mere presence of an edge or the absence of warnings.
    traces = {
        target: trace_dependencies(graph, f"{TOP}.{target}", "fanin",
                                   max_depth=12, max_edges=3000)
        for target in sorted(REQUIRED_OUTPUTS)
    }
    # The real ALU reads enum items defined in cv32e40p_pkg. Fail if this
    # semantic distinction regresses and they become fake RTL signal reads.
    enum_names = set(graph.get("resolved_enum_symbols", []))
    if "ALU_ADD" not in enum_names:
        raise AssertionError("ALU_ADD enum declaration not resolved from real slang AST")
    for name in ("result_o", "comparison_result_o"):
        response = traces[name]
        expected_sources = {
            f"{TOP}.operand_a_i", f"{TOP}.operand_b_i", f"{TOP}.operator_i"
        }
        missing = expected_sources - set(response["visited_nodes"])
        if missing or response["truncated"]:
            raise AssertionError(
                f"CV32E40P ALU {name} missing expected influences: {missing}, "
                f"truncated={response['truncated']}"
            )
    edge_types = dict(sorted(Counter(edge["kind"] for edge in graph["edges"]).items()))
    report = {
        "project": "OpenHW CV32E40P", "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_commit": UPSTREAM_COMMIT, "top": TOP,
        "sources": [{"relative_path": key, "sha256": hashlib.sha256(
            (source_root / key).read_bytes()).hexdigest()} for key in PINNED_BLOBS],
        "slang": subprocess.run(["slang", "--version"], capture_output=True,
                                text=True, check=True).stdout.strip(),
        "status": result["status"],
        "dependency_coverage": "partial" if graph["warnings"] else "within_supported_scope",
        "index_counts": index["counts"], "graph_counts": graph["counts"],
        "edge_types": edge_types, "ports": ports,
        "instance_paths": [item["path"] for item in index["instances"]],
        "resolved_parameter_symbols": graph.get("resolved_parameter_symbols", []),
        "resolved_enum_symbols": graph.get("resolved_enum_symbols", []),
        "fanin_outputs": {
            port: {"reachable_signals": len(trace["visited_nodes"]),
                   "truncated": trace["truncated"],
                   "has_operand_a": f"{TOP}.operand_a_i" in trace["visited_nodes"],
                   "has_operand_b": f"{TOP}.operand_b_i" in trace["visited_nodes"],
                   "has_operator": f"{TOP}.operator_i" in trace["visited_nodes"]}
            for port, trace in traces.items()
        },
        "warnings": graph["warnings"],
        "limitations": graph.get("limitations", []),
        "interpretation": "Real compilation and structural coverage are tested; this is NOT a functional proof.",
    }
    (out / "cv32e40p_alu_test_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {k: v for k, v in report.items()
               if k not in ("warnings", "ports", "resolved_parameter_symbols",
                            "resolved_enum_symbols")}
    summary["resolved_parameters_count"] = len(report["resolved_parameter_symbols"])
    summary["resolved_enum_count"] = len(report["resolved_enum_symbols"])
    summary["warning_examples"] = report["warnings"][:12]
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("reports/cv32e40p-alu"))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run_experiment(args.source_root, args.out, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
