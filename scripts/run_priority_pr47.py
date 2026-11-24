"""Run real slang NBA extraction, fixture simulation and isolated RAS mutations."""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from rtlprep.simulation import parse_cocotb_results
from scripts.run_cva6_ras import verify, TOP

FIXTURE=Path(__file__).resolve().parents[1]/"tests/fixtures/nba_priority_pr47.sv"
MUTATIONS={
    "simultaneous":("if (pop_i && push_i) begin","if (1'b0) begin"),
    "flush_priority":("if (flush_bp_i) begin","if (flush_bp_i && !push_i) begin"),
}
EXPECTED={
    "simultaneous":"scenario=simultaneous cycle=2 expected=(1, 51) actual=(1, 17)",
    "flush_priority":"scenario=flush_priority cycle=1 expected=(0, 0) actual=(1, 34)",
}

def mutate(text,variant):
    old,new=MUTATIONS[variant]
    if text.count(old)!=1 or new in text:
        raise ValueError("mutation anchor mismatch")
    return text.replace(old,new,1)

def detected(xml,variant):
    failures=ET.parse(xml).findall(".//failure")
    return len(failures)==1 and ("PR47_RAS_MISMATCH "+EXPECTED[variant]) in (str(failures[0].attrib)+" "+(failures[0].text or ""))

def simulate(sources,top,module,out,includes=()):
    from cocotb_tools.runner import get_runner
    out.mkdir(parents=True,exist_ok=True)
    xml=out/"simulation_results.xml"
    xml.unlink(missing_ok=True)
    runner=get_runner("verilator")
    runner.build(sources=sources,includes=list(includes),hdl_toplevel=top,
                 build_dir=out/"build",build_args=["--timing","-Wno-fatal"],
                 timescale=("1ns","1ps"),always=True,clean=True)
    runner.test(hdl_toplevel=top,test_module=module,build_dir=out/"build",
                test_dir=out,results_xml=str(xml),timescale=("1ns","1ps"))
    return parse_cocotb_results(xml),xml

def execute(root,out):
    root,out=root.resolve(),out.resolve()
    if out==root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("disjoint output required")
    sources=verify(root)
    hashes=lambda: [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
    before=hashes()
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/"priority.result.json"
    report_path.unlink(missing_ok=True)
    static=out/"static"
    static.mkdir(exist_ok=True)
    manifest=static/"design.json"
    manifest.write_text(json.dumps({"top":"nba_priority_pr47","sources":[str(FIXTURE)],"include_dirs":[],"defines":[]}))
    assert dependency_design(load_design(manifest),static,180)["status"]=="passed"
    graph=json.loads((static/"rtl_dependencies.json").read_text())
    rows=[r for r in graph["sequential_candidates"]["items"] if r["target"]=="nba_priority_pr47.q"]
    assert len(rows)==1 and rows[0]["coverage"]=="syntactic_candidates_supported",rows
    paths=rows[0]["paths"]
    both=[p for p in paths if p["write_count"]==2]
    assert len(both)==1 and both[0]["transition_candidate"]["rhs"]["path"]=="nba_priority_pr47.b",paths
    assert len(both[0]["local_overwritten_orders"])==1
    assert any(p["transition_candidate"]["kind"]=="unwritten_in_this_process" for p in paths)
    counts,_=simulate([FIXTURE],"nba_priority_pr47","rtlprep.sim_tests.nba_priority_pr47",out/"nba")
    assert (counts["passed"],counts["failed"],counts["skipped"])==(1,0,0)
    counts,_=simulate(sources,TOP,"rtlprep.sim_tests.cva6_ras_priority_pr47",out/"gold",[root/"core/include"])
    assert (counts["passed"],counts["failed"],counts["skipped"])==(2,0,0)
    results={}
    for variant in MUTATIONS:
        folder=out/variant
        generated=folder/"generated"
        generated.mkdir(parents=True,exist_ok=True)
        altered=generated/"ras.sv"
        altered.write_text(mutate(sources[-2].read_text(),variant))
        counts,xml=simulate(sources[:-2]+[altered,sources[-1]],TOP,
                            "rtlprep.sim_tests.cva6_ras_priority_pr47",folder,[root/"core/include"])
        assert (counts["passed"],counts["failed"],counts["skipped"])==(1,1,0),counts
        assert detected(xml,variant),variant
        results[variant]={"status":"expected_mutation_failure","expected_counterexample":EXPECTED[variant],
                          "mutant_sha256":hashlib.sha256(altered.read_bytes()).hexdigest()}
    verify(root)
    assert before==hashes()
    report={"status":"passed","nba_fixture_paths":paths,"nba_clocked_vectors":64,
            "ras_gold_tests":2,"ras_mutations":results,"source_sha256":before,
            "design_coverage":"not_measured","formal_proof":"not_performed",
            "scope":"fixture_full_width_local_NBA_and_real_RAS_blocking_priority"}
    report_path.write_text(json.dumps(report,indent=2))
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.source_root,a.out),indent=2))

if __name__=="__main__":
    main()
