"""Generate fresh static and behavioral evidence against one pinned snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.run_cva6_compressed_decoder import run_probe, verify_pinned_sources, WRAPPER, CHILD_INSTANCE, TOP, UPSTREAM_COMMIT
from scripts.run_cva6_compressed_oracle import run, MUTATIONS
from rtlprep.cva6_lane_evidence import compare_lanes

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def execute(root, out):
    root, out = root.resolve(), out.resolve()
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("source and output must be disjoint")
    sources, revision = verify_pinned_sources(root)
    if revision != "verified_exact_commit":
        raise ValueError("exact checkout required")
    tracked = sources + [WRAPPER.resolve()]
    before = [digest(p) for p in tracked]
    static = run_probe(root, out / "static")
    graph_path = out / "static/rtl_dependencies.json"
    graph = json.loads(graph_path.read_text())
    code, gold = run(root, out / "gold", "gold")
    if code != 0 or gold.get("completed_stimulus_vectors") != 9216:
        raise RuntimeError("gold suite failed")
    if gold.get("gold_source_sha256") != before[-2] or gold.get("top") != TOP or gold.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ValueError("gold snapshot mismatch")
    mutants = {}
    for family in MUTATIONS:
        code, report = run(root, out / family, family)
        if code != 2 or report.get("mutation_failure_evidence") is not True or report.get("gold_source_sha256") != before[-2]:
            raise RuntimeError("negative control failed: " + family)
        mutants[family] = {"status": report["status"], "expected_xor": MUTATIONS[family][3]}
    verify_pinned_sources(root)
    if before != [digest(p) for p in tracked]:
        raise ValueError("snapshot changed")
    result = compare_lanes(graph, child_instance=CHILD_INSTANCE, gold_passed=True)
    result.update({"upstream_commit": UPSTREAM_COMMIT, "configuration": static["configuration"],
                   "source_fingerprint": graph["source_fingerprint"], "source_sha256": before,
                   "graph_sha256": digest(graph_path), "gold_report_sha256": digest(out / "gold/cva6_compressed_simulation.result.json"),
                   "gold_completed_vectors": 9216, "negative_controls_by_family": mutants,
                   "negative_control_scope": "family_only_not_each_relation"})
    (out / "cva6_lane_evidence.json").write_text(json.dumps(result, indent=2))
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = execute(a.source_root, a.out)
    print(json.dumps(result["families"], indent=2))

if __name__ == "__main__":
    main()
