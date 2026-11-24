"""Check real slang complex-construct observations and independent behavior."""
import argparse
import json
from pathlib import Path
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.run_priority_pr47 import simulate

TOP="complex_pr53"
FIXTURE=Path(__file__).resolve().parents[1]/"tests/fixtures/complex_pr53.sv"

def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/"complex.result.json"
    report_path.unlink(missing_ok=True)
    manifest=out/"design.json"
    manifest.write_text(json.dumps({"top":TOP,"sources":[str(FIXTURE)],"include_dirs":[],"defines":[]}))
    assert dependency_design(load_design(manifest),out,180)["status"]=="passed"
    graph=json.loads((out/"rtl_dependencies.json").read_text())
    data=graph["complex_constructs"]
    items=data["items"]
    (out/"complex.diagnostic.json").write_text(json.dumps(data,indent=2))
    assert not data["counts"]["truncated"],data["counts"]
    calls=[r for r in items if r["kind"]=="call" and r["callee"]=="mix"]
    assert len(calls)==1,calls
    assert calls[0]["coverage"]=="partial"
    assert [a["signal_references"] for a in calls[0]["arguments"]]==[[TOP+".a"],[TOP+".b"]],calls
    selects=[r for r in items if r["kind"]=="selection" and TOP+".arr" in r["base_references"]["signal_references"]]
    assert any(s["literal_index"]==2 for r in selects for s in r["selectors"]),selects
    assert any(s["classification"]=="runtime_reference_candidate" and TOP+".idx" in s["signal_references"]
               for r in selects for s in r["selectors"]),selects
    loops=[r for r in items if r["kind"]=="loop"]
    assert any(r["ast_kind"]=="RepeatLoop" and r["literal_repeat_count"]==3 for r in loops),loops
    assert any(r["ast_kind"]=="ForLoop" and r["comparison_literal"]==4 for r in loops),loops
    assert all(r["unrolled"] is False and r["coverage"]=="partial" for r in loops)
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.complex_pr53",out/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
    report={"status":"passed","source_fingerprint":graph["source_fingerprint"],
            "construct_counts":data["counts"],"call_observations":calls,
            "selection_observations":selects,"loop_observations":loops,
            "behavioral_vectors":64,"scope":"fixture_only",
            "function_return_influence":"not_inferred","loop_unrolling":"not_performed",
            "formal_proof":"not_performed","design_coverage":"not_measured"}
    report_path.write_text(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    print(json.dumps(execute(p.parse_args().out),indent=2))
