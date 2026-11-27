"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.signed_shift_candidates import audit_signed_shifts
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="signed_shift_pr113"
FIXTURE=ROOT/"tests/fixtures/signed_shift_pr113.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(2,2,2,0,88,31),"alu":(98,6,6,0,698,154),
              "core":(384,6,6,0,698,154)}[name]
    assert tuple(c[k] for k in ("residual_ids","roots","supported","partial",
          "potential_pairs","stored_coordinates"))==expected,c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"] and c["nested_only_rows"]==0
    prefix=TOP+"." if name=="fixture" else ("cv32e40p_alu." if name=="alu" else "cv32e40p_core.ex_stage_i.alu_i.")
    wanted={}
    if name=="fixture":
        wanted[("y8",0,8)]=("d",0,"k",0,"mode")
        wanted[("y4",4,4)]=("d",4,"k",0,"mode")
    else:
        base_id=402 if name=="alu" else 724
        assert {r["flat_assignment_id"] for r in result["items"]}==set(range(base_id,base_id+6))
        slices=[(16,16),(0,16),(24,8),(16,8),(8,8),(0,8)]
        for i,(lo,n) in enumerate(slices):
            wanted[("shift_right_result",lo,n)]=("shift_op_a",lo,"shift_amt_int",lo,"shift_arithmetic")
            row=next(r for r in result["items"] if r["flat_assignment_id"]==base_id+i)
            assert row["candidate"]["target"]["bits_lsb_first"]==list(range(lo,lo+n))
    observed=set()
    for row in result["items"]:
        assert row["coverage"]=="signed_shift_candidates" and row["instance"]==prefix[:-1]
        x=row["candidate"];dst=x["target"];n=x["output_width"]
        m={4:2,8:3,16:4}[n]
        lo=dst["bits_lsb_first"][0]
        key=(dst["signal"].removeprefix(prefix),lo,n)
        assert key in wanted and key not in observed and dst["signal"]==prefix+key[0]
        observed.add(key)
        dn,dl,kn,kl,mode=wanted[key]
        assert dst["bits_lsb_first"]==list(range(lo,lo+n)) and not dst["outer_packed_indices"]
        assert x["operator"]=="ArithmeticShiftRight" and x["signed_intermediate_width"]==n+1
        assert x["data_width"]==n and x["amount_width"]==m
        assert x["operand_roles"]==["data","amount","sign_mode"]
        assert [(e["signal"],e["bits_lsb_first"]) for e in x["operands"]]==[
            (prefix+dn,list(range(dl,dl+n))),(prefix+kn,list(range(kl,kl+m))),(prefix+mode,[0])]
        assert all(not e["outer_packed_indices"] for e in x["operands"])
        assert x["sign_msb_evidence"]["signal"]==prefix+dn and x["sign_msb_evidence"]["bits_lsb_first"]==[dl+n-1]
        assert x["lane_support"]==[{"data_ordinals":list(range(i,n)),"amount_ordinals":list(range(m)),
                                   "mode_ordinals":[0] if i else []} for i in range(n)]
        assert x["potential_pairs"]==n*(n+1)//2+n*m+n-1
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
        result=audit_signed_shifts(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".signed-shifts.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.signed_shift_pr113",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","binary_input_vectors":4096,"output_checks_per_vector":2,
            "total_checks":8192,"source_sha256":file_sha(FIXTURE)}
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
