"""Real slang extraction and cocotb validation of event-local candidates."""
import argparse
import json
from pathlib import Path
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from rtlprep.intercycle import trace_event_candidates
from scripts.run_priority_pr47 import simulate

TOP="intercycle_pr51"
FIXTURE=Path(__file__).resolve().parents[1]/"tests/fixtures/intercycle_pr51.sv"

def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    result_path=out/"intercycle.result.json"
    result_path.unlink(missing_ok=True)
    manifest=out/"design.json"
    manifest.write_text(json.dumps({"top":TOP,"sources":[str(FIXTURE)],"include_dirs":[],"defines":[]}))
    assert dependency_design(load_design(manifest),out,180)["status"]=="passed"
    graph=json.loads((out/"rtl_dependencies.json").read_text())
    data=graph["intercycle_dependencies"]
    rows={r["target"]:r for r in data["items"]}
    assert len(rows)==4 and all(r["coverage"]=="syntactic_event_candidates_supported" for r in rows.values())
    for target,source in (("q1","data_i"),("q2","q1"),("q3","q2"),("cross_q","q3")):
        assert any(p["data_sources"]==[TOP+"."+source] for p in rows[TOP+"."+target]["paths"])
    assert any(p["relation"]=="local_hold_candidate" and p["control_sources"]==[TOP+".en"]
               for p in rows[TOP+".q3"]["paths"])
    trace=trace_event_candidates(data,TOP+".q3",max_steps=4)
    assert any([e["source"] for e in p["chain"]]==[TOP+".q2",TOP+".q1",TOP+".data_i"] for p in trace["paths"])
    cross=trace_event_candidates(data,TOP+".cross_q")
    assert len(cross["paths"])==1 and cross["paths"][0]["reason"]=="event_boundary"
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.intercycle_pr51",out/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
    result={"status":"passed","source_fingerprint":graph["source_fingerprint"],"candidate_counts":data["counts"],
            "pipeline_trace":trace,"cross_event_trace":cross,"clocked_vectors":64,
            "warmup_edges":3,"scope":"fixture_only","guaranteed_cycles":None,"formal_proof":"not_performed"}
    result_path.write_text(json.dumps(result,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    print(json.dumps(execute(p.parse_args().out),indent=2))
