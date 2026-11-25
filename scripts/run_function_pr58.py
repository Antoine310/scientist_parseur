"""Check real slang return-reference candidates and independent simulation."""
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
TOP="function_pr58"
FIXTURE=ROOT/"tests/fixtures/function_pr58.sv"


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
    data=graph["function_dependencies"]
    (run/"function.diagnostic.json").write_text(json.dumps(data,indent=2))
    rows={r["target"]:r for r in data["items"]}
    assert len(rows)==len(data["items"])==5 and not data["counts"]["truncated"],data
    expected={"mix_o":([0],[1],["a"]),"both_o":([0,1],[],["a","b"]),
              "cancel_o":([0],[],["a"])}
    for name,(used,unused,refs) in expected.items():
        row=rows[TOP+"."+name]
        assert row["coverage"]=="return_reference_candidates",row
        assert row["used_argument_positions"]==used,row
        assert row["unused_argument_positions"]==unused,row
        assert row["return_signal_references"]==[TOP+"."+r for r in refs],row
    for name in ("global_o","branch_o"):
        row=rows[TOP+"."+name]
        assert row["coverage"]=="partial" and "return_signal_references" not in row,row
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.function_pr58",run/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0),counts
    report={"status":"passed","source_fingerprint":graph["source_fingerprint"],
            "counts":data["counts"],"observations":data["items"],
            "behavioral_vectors":1024,"scope":"fixture_only",
            "functional_influence":"not_proven","formal_proof":"not_performed",
            "design_coverage":"not_measured"}
    path=run/"function.result.json"
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
