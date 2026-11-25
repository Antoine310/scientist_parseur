"""Check real slang static-loop positions and independent simulation."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.run_priority_pr47 import simulate
from scripts.run_scalability_pr55 import write_manifest
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="static_loops_pr59"
FIXTURE=ROOT/"tests/fixtures/static_loops_pr59.sv"


def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    manifest=run/"design.json"
    write_manifest(manifest,TOP,[FIXTURE])
    result=dependency_design(load_design(manifest),run,180)
    assert result["status"]=="passed",result
    graph=json.loads((run/"rtl_dependencies.json").read_text())
    data=graph["static_loop_expansion"]
    (run/"loops.diagnostic.json").write_text(json.dumps(data,indent=2))
    assert data["counts"]=={"captured":5,"supported":3,"partial":2,"edges":19,"truncated":False},data
    expected={(TOP+".a",7-i,TOP+".reverse_o",i,i,i) for i in range(8)}
    expected.update((TOP+".a",i,TOP+".identity_o",i,i,i) for i in range(8))
    expected.update((TOP+".a",0,TOP+".repeat_o",0,i,None) for i in range(3))
    actual={(e["source"],e["source_bit"],e["target"],e["target_bit"],
             e["iteration"],e["iterator_value"]) for e in data["edges"]}
    assert actual==expected and len(data["edges"])==19,{"missing":list(expected-actual),"extra":list(actual-expected)}
    assert sorted(r["iteration_count"] for r in data["items"] if r["coverage"]!="partial")==[3,8,8]
    assert {r["reason"] for r in data["items"] if r["coverage"]=="partial"}=={
        "nonliteral_header","iteration_budget_exceeded"},data
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.static_loops_pr59",run/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0),counts
    report={"status":"passed","source_fingerprint":graph["source_fingerprint"],
            "counts":data["counts"],"observations":data["items"],
            "reviewed_iteration_positions":19,"matched_iteration_positions":len(actual),
            "unique_source_target_bit_positions":len({e[:4] for e in actual}),
            "behavioral_vectors":768,"scope":"fixture_only",
            "functional_influence":"not_proven","formal_proof":"not_performed",
            "design_coverage":"not_measured"}
    path=run/"loops.result.json"
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
