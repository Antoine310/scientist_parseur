"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.concat_nba_targets import audit_concat_targets
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="concat_nba_pr106"
FIXTURE=ROOT/"tests/fixtures/concat_nba_pr106.sv"


def check(name,result):
    c=result["counts"]
    expected={"fixture":(2,2,2,0,0,6,3,3),"rxuart":(2,2,2,0,0,6,3,3),
              "alu":(0,0,0,0,0,0,0,0),"core":(5,0,0,0,5,0,0,0),
              "axis_register":(0,0,0,0,0,0,0,0),"priority_encoder":(0,0,0,0,0,0,0,0)}
    assert tuple(c[k] for k in ("historical_unsupported_targets","concat_sites","supported","partial",
                                "other_unsupported_targets","records","sampled","constant_zero"))==expected[name],c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0
    if name not in ("fixture","rxuart"):
        return
    owner=TOP if name=="fixture" else "rxuart"
    dst=["q","qq","ck"] if name=="fixture" else ["q_uart","qq_uart","ck_uart"]
    src=["serial_in","q","qq"] if name=="fixture" else ["i_uart_rx","q_uart","qq_uart"]
    expected_sample=[(i,owner+"."+d,owner+"."+s) for i,(d,s) in enumerate(zip(dst,src))]
    expected_zero=[(i,owner+"."+d,0) for i,d in enumerate(dst)]
    by_kind={}
    for row in result["items"]:
        assert row["historical_flat_assignment_id"] is None and row["instance"]==owner
        records=row["records"]
        assert all(x["target"]["bit"]==0 for x in records)
        rel={x["relation"] for x in records}
        assert len(rel)==1
        kind=next(iter(rel))
        assert kind not in by_kind
        if kind=="nba_sampled_position_candidate":
            assert all(x["source"]["bit"]==0 and x["constant"] is None for x in records)
            by_kind[kind]=[(x["concat_lsb_position"],x["target"]["signal"],x["source"]["signal"]) for x in records]
            if name=="rxuart": assert row["source_location"]["line"]==181
        else:
            assert kind=="nba_constant_zero_candidate" and all(x["source"] is None for x in records)
            by_kind[kind]=[(x["concat_lsb_position"],x["target"]["signal"],x["constant"]) for x in records]
            if name=="rxuart": assert row["source_location"]["line"]==179
    assert by_kind=={"nba_sampled_position_candidate":expected_sample,"nba_constant_zero_candidate":expected_zero}


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
        result=audit_concat_targets(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".concat-nba.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"input_sha256":before,"detail_file":detail.name,
             "detail_sha256":file_sha(detail),"audit_seconds":elapsed,"upstream":upstream,
             "historical_unchanged":True,**{k:v for k,v in result.items() if k not in ("items","other_unsupported_targets")}})
        save()
    try:
        extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture")
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.concat_nba_pr106",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","binary_transition_checks":32,"setup_checks":128,
            "total_checks":160,"source_sha256":file_sha(FIXTURE)}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
        for e in lock:
            if e["repository"] not in ("alexforencich/verilog-axis","ZipCPU/wbuart32"): continue
            root=ROOT/e["destination"]
            verify_checkout(root,e)
            for src in e["blobs"]:
                name=Path(src).stem
                folder=run/name
                extract(folder,name,[root/src])
                case(name,folder,{"repository":e["repository"],"commit":e["commit"],"blob":e["blobs"][src]})
            verify_checkout(root,e)
        assert len(report["cases"])==6
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
