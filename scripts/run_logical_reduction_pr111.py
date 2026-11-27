"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.logical_candidates import audit_logical
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="logical_reduction_pr111"
FIXTURE=ROOT/"tests/fixtures/logical_reduction_pr111.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(6,6,6,0,23,29),"alu":(98,0,0,0,0,0),
              "core":(384,69,4,65,11,15)}[name]
    assert tuple(c[k] for k in ("residual_ids","roots","supported","partial",
          "potential_pairs","stored_coordinates"))==expected,c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    actual={}
    for row in result["items"]:
        if row["coverage"]=="partial":
            assert row.get("reason")
            continue
        cand=row["candidate"]
        ep=cand["target"]
        assert ep["signal"]==row["target"] and len(ep["bits_lsb_first"])==1
        key=(ep["signal"],ep["bits_lsb_first"][0])
        assert key not in actual
        actual[key]=[(s["signal"],tuple(s["bits_lsb_first"])) for s in cand["operands"]]
    wanted={}
    if name=="fixture":
        prefix=TOP+"."
        inputs=[["a","b"],["a","b","c"],["a","b","c","d"],["v","d"],["v","b"],["v"]]
        wanted={(prefix+"y",i):[(prefix+v,tuple(range(4)) if v=="v" else (0,)) for v in values]
                for i,values in enumerate(inputs)}
    elif name=="core":
        p="cv32e40p_core.id_stage_i.controller_i."
        for i in range(2):
            wanted[(p+"hwlp_dec_cnt_o",i)]=[(p+f"hwlp_end{i}_eq_pc",(0,)),(p+f"hwlp_counter{i}_eq_0",(0,))]
        p="cv32e40p_core.cs_registers_i."
        for i in (0,2):
            wanted[(p+"mhpmcounter_write_increment",i)]=[(p+k,(i,)) for k in
                ("mhpmcounter_write_lower","mhpmcounter_write_upper","mcountinhibit_q")]
        wanted[(p+"mhpmcounter_write_increment",2)].append((p+"hpm_events",(1,)))
        assert {r["flat_assignment_id"] for r in result["items"] if r["coverage"]!="partial"}=={182,183,882,883}
        assert {r["flat_assignment_id"] for r in result["items"]}=={182,183,184,*range(214,278),882,883}
    assert actual==wanted,(actual,wanted)


def execute(out,reference=None):
    out=out.resolve()
    lock=load_lock()
    for e in lock:
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","rtl_equivalence":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,upstream=None):
        before={k:file_sha(folder/k) for k in INPUTS}
        ast=read_ast(folder/INPUTS[0])
        idx=json.loads((folder/INPUTS[1]).read_text())
        g=json.loads((folder/INPUTS[2]).read_text())
        start=perf_counter()
        result=audit_logical(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".logical-reduction.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"input_sha256":before,"detail_file":detail.name,
             "detail_sha256":file_sha(detail),"audit_seconds":elapsed,"upstream":upstream,
             "historical_unchanged":True,**{k:v for k,v in result.items() if k not in ("items","nested_only_ids")}})
        save()
    try:
        extract_fixture(run/"fixture")
        case("fixture",run/"fixture")
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.logical_reduction_pr111",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","binary_input_vectors":256,"output_checks_per_vector":6,
            "total_checks":1536,"source_sha256":file_sha(FIXTURE)}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
        assert len(report["cases"])==3
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:3000])
        raise
    finally:
        save()
        print(path.read_text(),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--reference",type=Path)
    a=p.parse_args()
    execute(a.out,a.reference)
