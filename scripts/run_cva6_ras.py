"""Probe real CVA6 RAS, retaining unsupported sequential paths explicitly."""
import argparse
import json
import hashlib
import subprocess
from pathlib import Path
from rtlprep.field_validation import git_blob_sha1
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design, fingerprint
from scripts.run_cva6_compressed_decoder import PINNED_SOURCES, UPSTREAM_COMMIT

TOP = "rtlprep_cva6_ras"
TARGET = TOP + ".ras_i.stack_q"
SOURCES = PINNED_SOURCES[:4] + (("core/frontend/ras.sv", "422a829fa4c1d4d4fa3b1c78cf38337003887de1"),)
WRAPPER = Path(__file__).resolve().parents[1] / "tests/fixtures/cva6/ras_probe.sv"

def verify(root):
    if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip() != UPSTREAM_COMMIT:
        raise ValueError("unexpected CVA6 revision")
    paths = []
    for name, sha in SOURCES:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or git_blob_sha1(path.read_bytes()) != sha:
            raise ValueError("source mismatch: " + name)
        paths.append(path)
    return paths + [WRAPPER.resolve()]

def summarize(graph):
    if graph.get("top") != TOP or graph.get("schema_version") != 1:
        raise ValueError("wrong graph")
    flow = graph["register_flow"]
    seq = graph["sequential_candidates"]
    rows = [r for r in flow["items"] if r["target"] == TARGET]
    candidates = [r for r in seq["items"] if r["target"] == TARGET]
    return {"target": TARGET, "flow_records": rows, "transition_candidates": candidates,
            "flow_counts": flow["counts"], "sequential_counts": seq["counts"],
            "status": "observed" if rows else "not_observed",
            "design_coverage": "not_measured", "formal_proof": "not_performed",
            "next_state_combinational_semantics": "not_proven"}

def run(root, out):
    root, out = root.resolve(), out.resolve()
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("output must be disjoint from source")
    paths = verify(root)
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "design.json"
    manifest.write_text(json.dumps({"top":TOP,"sources":[str(p) for p in paths],
                                   "include_dirs":[str(root/"core/include")],"defines":[]}))
    design = load_design(manifest)
    fp = fingerprint(design)
    result = dependency_design(design,out,240)
    if result.get("status") != "passed":
        raise RuntimeError("elaboration failed: " + str(result))
    graph = json.loads((out/"rtl_dependencies.json").read_text())
    if graph.get("source_fingerprint") != fp or fingerprint(design) != fp:
        raise ValueError("graph snapshot mismatch")
    verify(root)
    if before != [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]:
        raise ValueError("source changed")
    report = summarize(graph)
    report.update({"upstream_commit":UPSTREAM_COMMIT,"configuration":"cv32a6_imac_sv32",
                   "depth":2,"source_fingerprint":fp,"source_sha256":before,
                   "warnings":graph["warnings"],"graph_counts":graph["counts"],
                   "behavioral_validation":"not_performed_by_static_probe"})
    (out/"cva6_ras_report.json").write_text(json.dumps(report,indent=2))
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a = p.parse_args()
    print(json.dumps(run(a.source_root,a.out),indent=2))

if __name__ == "__main__":
    main()
