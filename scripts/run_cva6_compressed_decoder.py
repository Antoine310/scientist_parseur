"""First real OpenHW CVA6 compressed-decoder probe with a pinned RV32 configuration.

External RTL is fetched separately at the exact revision below. This is an
AST / dependency-graph observation, not functional verification of CVA6.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from rtlprep.dependencies import trace_dependencies
from rtlprep.field_validation import git_blob_sha1
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design, fingerprint

UPSTREAM_REPOSITORY = "openhwfoundation/cva6"
UPSTREAM_COMMIT = "742dc82a0c706e0a3bfb98b709fd3ee06d50d12a"
CONFIGURATION = "cv32a6_imac_sv32"
TOP = "rtlprep_cva6_compressed_decoder"
CHILD_INSTANCE = TOP + ".decoder_i"
INPUT = "instr_i"
OUTPUTS = (
    "instr_o", "illegal_instr_o", "is_macro_instr_o",
    "is_compressed_o", "is_zcmt_instr_o",
)
# Git blob hashes of actual upstream bytes at UPSTREAM_COMMIT; no vendored RTL.
PINNED_SOURCES = (
    ("core/include/config_pkg.sv", "a68b2c14ea758bc820a35cc3ac27035359763d0a"),
    ("core/include/cv32a6_imac_sv32_config_pkg.sv", "d0824c0b8202b1f2b048864f502ba2c7b2375e8f"),
    ("core/include/riscv_pkg.sv", "146bcc2c307ec236c3c0ca3854ca69ce6fdcecb9"),
    ("core/include/build_config_pkg.sv", "429080949a6626f4f42cdb1c717383bb3b7f3843"),
    ("core/compressed_decoder.sv", "76385e5ea0b9eb0cc2d0e96fe978a90d4e122c19"),
)
WRAPPER = (Path(__file__).resolve().parents[1] /
           "tests/fixtures/cva6/compressed_decoder_probe.sv")


def verify_pinned_sources(root: Path) -> tuple[list[Path], str]:
    """Reject missing/changed/escaped sources before invoking the EDA tool."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"CVA6 source checkout absent: {root}")
    sources: list[Path] = []
    for relative, expected in PINNED_SOURCES:
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f"CVA6 source missing or outside checkout: {relative}")
        actual = git_blob_sha1(source.read_bytes())
        if actual != expected:
            raise ValueError(
                f"CVA6 git blob mismatch: {relative}; expected {expected}, got {actual}"
            )
        sources.append(source)

    # A sparse checkout can prove both the revision and the blob contents.
    # A plain downloaded tree proves only blob contents, never commit identity.
    revision = "not_checked_no_git_checkout"
    if (root / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, timeout=20,
        )
        if proc.returncode != 0:
            raise ValueError("Cannot verify CVA6 checkout revision")
        actual_commit = proc.stdout.strip()
        if actual_commit != UPSTREAM_COMMIT:
            raise ValueError(
                f"Unexpected CVA6 checkout: expected {UPSTREAM_COMMIT}, got {actual_commit}"
            )
        revision = "verified_exact_commit"
    return sources, revision


def run_probe(source_root: Path, out: Path, *, timeout: int = 180) -> dict:
    if type(timeout) is not int or not 1 <= timeout <= 900:
        raise ValueError("timeout must be an integer in [1, 900]")
    root = source_root.expanduser().resolve()
    output = out.expanduser().resolve()
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Output directory and upstream source checkout must be disjoint")

    sources, revision_status = verify_pinned_sources(root)
    if not WRAPPER.is_file():
        raise FileNotFoundError(f"RTLPrep CVA6 wrapper missing: {WRAPPER}")
    sources.append(WRAPPER.resolve())
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "design.json"
    manifest.write_text(json.dumps({
        "top": TOP,
        "sources": [str(p) for p in sources],
        "include_dirs": [str(root / "core/include")],
        "defines": [],
    }, indent=2), encoding="utf-8")
    design = load_design(manifest)
    before = fingerprint(design)
    result = dependency_design(design, output, timeout)
    if result.get("status") != "passed":
        raise RuntimeError(
            f"slang / RTLPrep did not complete: {result.get('status')}; "
            f"{result.get('error', 'see analyze.stderr.log and deps.result.json')}"
        )
    if fingerprint(design) != before:
        raise ValueError("CVA6 source snapshot changed during analysis")
    # Re-check source integrity even if a file was changed and restored at
    # another path; the manifest/fingerprint covers the wrapper as well.
    verify_pinned_sources(root)
    index = json.loads((output / "rtl_index.json").read_text(encoding="utf-8"))
    graph = json.loads((output / "rtl_dependencies.json").read_text(encoding="utf-8"))
    if (index.get("top") != TOP or graph.get("top") != TOP
            or index.get("source_fingerprint") != before
            or graph.get("source_fingerprint") != before):
        raise AssertionError("Index / graph do not match pinned CVA6 snapshot")
    if graph.get("coverage", {}).get("design_coverage") != "not_measured":
        raise AssertionError("An exhaustive design-coverage claim was introduced")
    instances = {row["path"]: row for row in index["instances"]}
    if TOP not in instances or CHILD_INSTANCE not in instances:
        raise AssertionError("CVA6 decoder instance missing from elaborated hierarchy")
    ports = {p["name"]: p["direction"] for p in instances[TOP]["ports"]}
    if ports.get(INPUT) != "In" or any(ports.get(p) != "Out" for p in OUTPUTS):
        raise AssertionError(f"Unexpected CVA6 harness ports: {ports}")
    nodes = set(graph["nodes"])
    if not graph["edges"] or any(f"{TOP}.{p}" not in nodes for p in (INPUT, *OUTPUTS)):
        raise AssertionError("Empty / missing CVA6 dependency graph or output nodes")

    fanin = {}
    for name in OUTPUTS:
        response = trace_dependencies(
            graph, f"{TOP}.{name}", direction="fanin",
            max_depth=12, max_edges=2500,
        )
        fanin[name] = {
            "visited_nodes": len(response["visited_nodes"]),
            "observed_input_reachable": f"{TOP}.{INPUT}" in response["visited_nodes"],
            "truncated": bool(response["truncated"]),
            "returned_edges": len(response["edges"]),
        }

    warnings = graph["warnings"]
    coverage = graph["coverage"]
    report = {
        "schema_version": 1,
        "project": "OpenHW CVA6",
        "module": "compressed_decoder",
        "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_commit": UPSTREAM_COMMIT,
        "source_integrity": "verified_pinned_git_blobs",
        "checkout_revision_status": revision_status,
        "configuration": CONFIGURATION,
        "top": TOP,
        "child_instance": CHILD_INSTANCE,
        "slang": subprocess.run(
            ["slang", "--version"], capture_output=True, text=True,
            check=True, timeout=20,
        ).stdout.strip(),
        "sources": [
            {"path": rel, "git_blob_sha1": blob}
            for rel, blob in PINNED_SOURCES
        ],
        "harness": str(WRAPPER.relative_to(WRAPPER.parents[3])),
        "elaboration": "passed",
        "ports": ports,
        "index_counts": index["counts"],
        "graph_counts": graph["counts"],
        "edge_types": dict(sorted(Counter(edge["kind"] for edge in graph["edges"]).items())),
        "fanin_outputs": fanin,
        "warnings_total": len(warnings),
        "warnings_sample": warnings[:20],
        "observed_analyzers": {
            name: {
                "counts": graph[name]["counts"],
                "scope": graph[name].get("scope"),
            } for name in ("expressions", "register_flow", "bit_accesses")
        },
        "coverage_assessment": coverage["assessment"],
        "design_coverage": "not_measured",
        "functional_correctness": "not_tested",
        "accuracy": "not_measured_without_independent_exhaustive_oracle",
        "benchmarked_llm": False,
        "limitations": graph.get("limitations", []),
        "interpretation": (
            "Observed elaborated AST and signal-level possible dependencies "
            "for one upstream CVA6 configuration. No bit-accurate, "
            "cycle-accurate, exhaustive or functional correctness claim."
        ),
    }
    path = output / "cva6_compressed_decoder_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("reports/cva6-compressed-decoder"))
    p.add_argument("--timeout", type=int, default=180)
    args = p.parse_args()
    report = run_probe(args.source_root, args.out, timeout=args.timeout)
    print(json.dumps({
        "report": str((args.out / "cva6_compressed_decoder_report.json").resolve()),
        "upstream_commit": report["upstream_commit"],
        "configuration": report["configuration"],
        "elaboration": report["elaboration"],
        "checkout_revision_status": report["checkout_revision_status"],
        "graph_counts": report["graph_counts"],
        "warnings_total": report["warnings_total"],
        "fanin_outputs": report["fanin_outputs"],
        "design_coverage": report["design_coverage"],
        "accuracy": report["accuracy"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
