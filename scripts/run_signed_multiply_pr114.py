"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.multiply_candidates import audit_multiplications
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="signed_multiply_pr114"
FIXTURE=ROOT/"tests/fixtures/signed_multiply_pr114.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(4,4,4,0,1240,136,0),"alu":(98,0,0,0,0,0,38),
              "core":(384,6,6,0,2776,280,38)}[name]
    assert tuple(c[k] for k in ("residual_ids","roots","supported","partial",
          "potential_pairs","stored_coordinates","nested_only_rows"))==expected,c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    if name=="alu":
        assert not result["items"]
        return
    prefix=TOP+"." if name=="fixture" else "cv32e40p_core.ex_stage_i.mult_i."
    wanted={}
    if name=="fixture":
        for i in range(2):
            wanted[("p4",(i,))]=(4,"a4",[i],"b4",[i])
        for n in (9,17):
            wanted[(f"p{n}",(0,))]=(n,f"a{n}",[0],f"b{n}",[0])
    else:
        assert {r["flat_assignment_id"] for r in result["items"]}=={805,806,807,808,817,818}
        for i in range(4):
            wanted[("dot_char_mul",(i,))]=(9,"dot_char_op_a",[i],"dot_char_op_b",[i])
        wanted[("dot_short_mul",(0,))]=(17,"dot_short_op_a",[0],"dot_short_op_b",[0])
        wanted[("dot_short_mul",(1,))]=(17,"dot_short_op_a_1_neg",[],"dot_short_op_b",[1])
    observed=set()
    for row in result["items"]:
        assert row["coverage"]=="multiply_candidates" and row["instance"]==prefix[:-1]
        x=row["candidate"];dst=x["target"]
        key=(dst["signal"].removeprefix(prefix),tuple(dst["outer_packed_indices"]))
        assert key in wanted and key not in observed and dst["signal"]==prefix+key[0]
        observed.add(key)
        n,an,ai,bn,bi=wanted[key]
        assert x["operator"]=="Multiply" and x["operand_width"]==n and x["output_width"]==2*n
        assert dst["bits_lsb_first"]==list(range(2*n))
        assert [(e["signal"],e["outer_packed_indices"],e["bits_lsb_first"]) for e in x["operands"]]==[
            (prefix+an,ai,list(range(n))),(prefix+bn,bi,list(range(n)))]
        assert all(e["extension"]=={"kind":"signed_reinterpret_then_sign_extend","from_width":n,"to_width":2*n}
                   for e in x["operands"])
        # Independent per-lane low-bit bound, witness -1 (or +1 for sign bit).
        assert x["prefix_lengths"]==[len([j for j in range(n) if j<=i]) for i in range(2*n)]
        assert x["potential_pairs"]==3*n*n+n
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
        result=audit_multiplications(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".signed-multiplies.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.signed_multiply_pr114",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","exhaustive_4bit_input_pairs":256,"boundary_9_17bit_input_pairs_each":144,
            "total_checks":800,"source_sha256":file_sha(FIXTURE)}
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
