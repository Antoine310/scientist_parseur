"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.initial_zero_candidates import audit_initial_zero
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="initial_zero_pr110"
FIXTURE=ROOT/"tests/fixtures/initial_zero_pr110.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(8,5,5,3,2,13,0,0),"alu":(612,0,0,0,0,0,0,0),
              "core":(3811,0,0,0,0,0,0,5),"axis_register":(44,0,0,0,0,0,0,0),
              "priority_encoder":(9,0,0,0,0,0,0,0),"rxuart":(87,15,15,13,2,47,0,2)}
    assert tuple(c[k] for k in ("ast_occurrences","historical_nonvisited","initial_sites","supported","partial",
          "records","other_nonvisited","historical_unsupported_targets"))==expected[name],c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==result["permanent_constants_inferred"]==0
    if name not in ("fixture","rxuart"):
        return
    owner=TOP if name=="fixture" else "rxuart"
    expected_targets={"flag_q":[0],"word_q":list(range(2,6)),"byte_q":list(range(8))} if name=="fixture" else {
          **{k:[0] for k in ("q_uart","qq_uart","ck_uart","o_break","line_synch","half_baud_time",
                            "o_parity_err","o_frame_err","pre_wr","o_wr","zero_baud_counter")},
          "chg_counter":list(range(28)),"o_data":list(range(8))}
    observed={}
    refused=[]
    for row in result["items"]:
        assert row["instance"]==owner and row["historical_flat_assignment_id"] is None
        assert row["boundary"]["procedure_kind"]=="Initial"
        if row["coverage"]=="partial":
            assert not row["records"]
            refused.append(row)
            continue
        records=row["records"]
        assert all(r["relation"]=="initial_zero_assignment_candidate" and r["value"]==0
                   and r["lifetime"]=="statement_local_startup_only" for r in records)
        signals={r["target"]["signal"] for r in records}
        assert len(signals)==1
        target=next(iter(signals)).removeprefix(owner+".")
        assert target not in observed
        observed[target]=[r["target"]["bit"] for r in records]
    assert observed==expected_targets,(observed,expected_targets)
    if name=="rxuart":
        assert {r["source_location"]["line"] for r in refused}=={262,298}
    else:
        assert {r["reason"] for r in refused}=={"not_explicit_binary_defined_zero","not_literal_or_zero_conversion"}


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
        result=audit_initial_zero(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".initial-zero.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"input_sha256":before,"detail_file":detail.name,
             "detail_sha256":file_sha(detail),"audit_seconds":elapsed,"upstream":upstream,
             "historical_unchanged":True,**{k:v for k,v in result.items() if k not in ("items","other_nonvisited")}})
        save()
    try:
        extract_fixture(run/"fixture")
        case("fixture",run/"fixture")
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.initial_zero_pr110",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","startup_checks":3,"binary_input_vectors":256,"output_checks_per_vector":3,
            "total_checks":771,"source_sha256":file_sha(FIXTURE)}
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
