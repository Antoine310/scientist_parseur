"""Compare unchanged PR56 annotations and an independent generated-lane fixture."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.run_annotated_pr56 import execute as evaluate
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock
from scripts.run_scalability_pr55 import write_manifest

ROOT=Path(__file__).resolve().parents[1]
TOP="constant_indices_pr57"
FIXTURE=ROOT/"tests/fixtures/constant_indices_pr57.sv"


def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    eval_path=evaluate(run/"annotated")
    evaluation=json.loads(eval_path.read_text(encoding="utf-8"))
    cases={c["name"]:c for c in evaluation["cases"]}
    for name,channel,expected in (("fixture","signal",10),("fixture","bit",16),
                                  ("cv32e40p_alu","signal",10),("cv32e40p_alu","bit",65)):
        result=cases[name][channel]
        assert (result["tp"],result["fp"],result["fn"])==(expected,0,0),{
            "case":name,"channel":channel,"result":result}
    holdout=run/"holdout"
    holdout.mkdir()
    manifest=holdout/"design.json"
    write_manifest(manifest,TOP,[FIXTURE])
    result=dependency_design(load_design(manifest),holdout,180)
    assert result["status"]=="passed",result
    graph=json.loads((holdout/"rtl_dependencies.json").read_text(encoding="utf-8"))
    bit=graph["bit_dependency_graph"]
    expected={(f"{TOP}.{inst}.a",source,f"{TOP}.{inst}.perm",
               2*(3-source//2)+source%2)
              for inst in ("u0","u1") for source in range(8)}
    actual={(e["source"],e["source_bit"],e["target"],e["target_bit"]) for e in bit["edges"]}
    assert actual==expected and len(bit["edges"])==16 and not bit["counts"]["truncated"],{
        "missing":sorted(expected-actual),"unexpected":sorted(actual-expected),"counts":bit["counts"]}
    for inst in ("u0","u1"):
        rows=[r for r in bit["items"] if r["target"]==f"{TOP}.{inst}.dynamic_o"]
        assert len(rows)==1 and rows[0]["coverage"]=="partial" and rows[0]["edge_count"]==0,rows
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.constant_indices_pr57",holdout/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0),counts
    alu=cases["cv32e40p_alu"]["bit"]
    report={"status":"passed","annotation_sha256":evaluation["annotation_sha256"],
            "baseline_pr56_alu_bit":{"tp":1,"fp":0,"fn":64,"positive_labels":65},
            "current_alu_bit":alu,"recovered_labelled_positives":alu["tp"]-1,
            "holdout":{"expected_edges":16,"matched_edges":len(actual),"dynamic_rejections":2,
                       "behavioral_vectors":256,"source_fingerprint":graph["source_fingerprint"]},
            "formal_proof":"not_performed","design_coverage":"not_measured",
            "scope":"frozen_pilot_and_separate_fixture_only"}
    path=run/"constant_indices.result.json"
    path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    print(f"Report: {path}")
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
