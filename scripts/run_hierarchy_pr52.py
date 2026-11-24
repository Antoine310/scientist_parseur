"""Validate hierarchical candidate traces against real slang and simulation."""
import argparse
import json
from pathlib import Path
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from rtlprep.hierarchy import trace_hierarchical
from scripts.run_priority_pr47 import simulate

TOP="hierarchy_pr52"
FIXTURE=Path(__file__).resolve().parents[1]/"tests/fixtures/hierarchy_pr52.sv"

def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/"hierarchy.result.json"
    report_path.unlink(missing_ok=True)
    manifest=out/"design.json"
    manifest.write_text(json.dumps({"top":TOP,"sources":[str(FIXTURE)],"include_dirs":[],"defines":[]}))
    assert dependency_design(load_design(manifest),out,180)["status"]=="passed"
    graph=json.loads((out/"rtl_dependencies.json").read_text())
    result=trace_hierarchical(graph,TOP+".result_o")
    cross=trace_hierarchical(graph,TOP+".cross_o")
    (out/"hierarchy.diagnostic.json").write_text(json.dumps({"pipeline":result,"cross":cross,
         "bindings":graph["hierarchical_event_bindings"]},indent=2))
    expected=[TOP+".pair_i.b.q",TOP+".pair_i.a.q"]
    assert not result["truncated"] and not cross["truncated"]
    matches=[p for p in result["paths"] if p["boundary"]==TOP+".data_i" and p["event_steps"]==2]
    assert matches,result
    assert any([e["target"] for e in p["chain"] if "local_event" in e]==expected
               and all(e["event_identity_candidate"]=={"edge":"PosEdge","signal":TOP+".clk"}
                       for e in p["chain"] if "local_event" in e) for p in matches),result
    assert any(p["reason"]=="event_boundary" and p["boundary"]==TOP+".pair_i.b.q"
               and p["event_steps"]==1 for p in cross["paths"]),cross
    assert not any(p["boundary"]==TOP+".data_i" for p in cross["paths"]),cross
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.hierarchy_pr52",out/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
    report={"status":"passed","source_fingerprint":graph["source_fingerprint"],
            "pipeline_trace":result,"cross_event_trace":cross,
            "scalar_input_bindings":graph["hierarchical_event_bindings"]["items"],
            "clocked_vectors":64,"warmup_edges":2,"scope":"fixture_only",
            "guaranteed_cycles":None,"formal_proof":"not_performed"}
    report_path.write_text(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    print(json.dumps(execute(p.parse_args().out),indent=2))
