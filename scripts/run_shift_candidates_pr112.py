"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.shift_candidates import audit_shifts
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="shift_candidates_pr112"
FIXTURE=ROOT/"tests/fixtures/shift_candidates_pr112.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(4,4,4,0,233,87),"alu":(98,8,2,6,1313,138),
              "core":(384,8,2,6,1313,138)}[name]
    assert tuple(c[k] for k in ("residual_ids","roots","supported","partial",
          "potential_pairs","stored_coordinates"))==expected,c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    if name!="fixture":
        expected_ids={69,408} if name=="alu" else {391,730}
        assert {r["flat_assignment_id"] for r in result["items"] if r["coverage"]!="partial"}==expected_ids
        assert {r["flat_assignment_id"] for r in result["items"]}==( {69,*range(402,409)} if name=="alu" else {391,*range(724,731)})
        assert c["nested_only_rows"]==(0 if name=="alu" else 1)
    prefix=TOP+"." if name=="fixture" else ("cv32e40p_alu." if name=="alu" else "cv32e40p_core.ex_stage_i.alu_i.")
    wanted={"fixed_o":("LogicalShiftLeft",8,8,0,2,None,["d"],[list(range(8))]),
            "left_o":("LogicalShiftLeft",8,8,3,None,None,["d","k"],[list(range(8)),list(range(3))]),
            "right_o":("LogicalShiftRight",8,4,3,None,None,["d","k"],[list(range(8)),list(range(3))]),
            "mask_o":("LogicalShiftLeft",32,32,5,None,0xfffffffe,["k"],[list(range(5))])} if name=="fixture" else {
            "bmask_first":("LogicalShiftLeft",32,32,5,None,0xfffffffe,["bmask_a_i"],[list(range(5))]),
            "shift_right_result":("LogicalShiftRight",64,32,5,None,None,["shift_op_a_32","shift_amt_int"],[list(range(64)),list(range(5))])}
    observed=set()
    for row in result["items"]:
        if row["coverage"]=="partial":
            assert row["reason"]=="signed_or_arithmetic_shift_outside_scope"
            continue
        cand=row["candidate"];dst=cand["target"]
        key=dst["signal"].removeprefix(prefix)
        assert key in wanted and key not in observed and dst["signal"]==prefix+key
        observed.add(key)
        op,w,n,m,k,mask,names,bits=wanted[key]
        assert (cand["operator"],cand["data_width"],cand["output_width"],cand["amount_width"],
                cand["constant_amount"],cand["constant_data"])==(op,w,n,m,k,mask)
        assert dst["bits_lsb_first"]==list(range(n))
        assert [(e["signal"],e["bits_lsb_first"]) for e in cand["operands"]]==list(zip([prefix+x for x in names],bits))
        for i,l in enumerate(cand["lane_support"]):
            if mask is not None:
                ds=[];cs=[b for b in range(5) if any((a<i)!=((a^(1<<b))<i) for a in range(32))]
                fixed=0 if i==0 else None
            elif k is not None:
                ds=[i-k] if i>=k else [];cs=[];fixed=None if ds else 0
            else:
                ds=list(range(max(0,i-(2**m-1)),i+1)) if op=="LogicalShiftLeft" else list(range(i,min(w,i+2**m)))
                cs=list(range(m));fixed=None
            assert l=={"data_ordinals":ds,"amount_ordinals":cs,"constant_value":fixed},(key,i,l)
    assert observed==set(wanted)


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
        result=audit_shifts(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".shifts.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.shift_candidates_pr112",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","binary_input_vectors":8192,"output_checks_per_vector":4,
            "total_checks":32768,"source_sha256":file_sha(FIXTURE)}
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
