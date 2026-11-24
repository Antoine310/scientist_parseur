"""Verify real slang bit candidates and exhaustive eight-bit fixture behavior."""
import argparse
import json
from pathlib import Path
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.run_priority_pr47 import simulate

TOP="bitgraph_pr54"
FIXTURE=Path(__file__).resolve().parents[1]/"tests/fixtures/bitgraph_pr54.sv"

def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/"bitgraph.result.json"
    report_path.unlink(missing_ok=True)
    manifest=out/"design.json"
    manifest.write_text(json.dumps({"top":TOP,"sources":[str(FIXTURE)],"include_dirs":[],"defines":[]}))
    assert dependency_design(load_design(manifest),out,180)["status"]=="passed"
    graph=json.loads((out/"rtl_dependencies.json").read_text())
    data=graph["bit_dependency_graph"]
    (out/"bitgraph.diagnostic.json").write_text(json.dumps(data,indent=2))
    # Independently reviewed source/destination bit positions, not generated
    # from the analyzer's segments.
    expected=set()
    def add(target,source_bit,target_bit,transform="position_only"):
        expected.add((TOP+".a",source_bit,TOP+"."+target,target_bit,transform))
    for i in range(4):
        add("swap_o",i,i+4)
        add("swap_o",i+4,i)
        add("shifted_o",i,i+8)
        add("shifted_o",i+4,i+4,"bitwise_not")
        add("constant_o",i,i)
    for i in range(4):
        add("replicated_o",i%2,i)
    actual={(e["source"],e["source_bit"],e["target"],e["target_bit"],e["value_transform"])
            for e in data["edges"]}
    assert not data["counts"]["truncated"]
    assert actual==expected and len(data["edges"])==len(expected),{
        "missing":sorted(expected-actual),"unexpected":sorted(actual-expected),
        "counts":data["counts"]}
    constants=[r for r in data["items"] if r["target"]==TOP+".constant_o"]
    assert len(constants)==1 and constants[0]["constant_target_bits"]==[4,5,6,7],constants
    for target in ("dynamic_o","indexed_o","array_o"):
        rows=[r for r in data["items"] if r["target"]==TOP+"."+target]
        assert rows and all(r["coverage"]=="partial" and r["edge_count"]==0 for r in rows),rows
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.bitgraph_pr54",out/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
    report={"status":"passed","source_fingerprint":graph["source_fingerprint"],
            "bit_graph_counts":data["counts"],"reviewed_edges":len(expected),
            "matched_edges":len(actual),"constant_target_bits":4,
            "unsupported_targets_checked":["dynamic_o","indexed_o","array_o"],
            "behavioral_vectors":256,"scope":"fixture_only",
            "formal_proof":"not_performed","design_coverage":"not_measured",
            "functional_influence":"not_proven"}
    report_path.write_text(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    print(json.dumps(execute(p.parse_args().out),indent=2))
