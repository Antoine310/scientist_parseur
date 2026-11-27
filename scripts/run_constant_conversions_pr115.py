"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.constant_conversion_candidates import audit_constant_conversions
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="constant_conversions_pr115"
FIXTURE=ROOT/"tests/fixtures/constant_conversions_pr115.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(12,12,0,388),"alu":(32,32,0,160),
              "core":(94,93,1,3024)}[name]
    assert tuple(c[k] for k in ("roots","supported","partial","value_records"))==expected,c
    assert c["potential_pairs"]==0 and c["stored_coordinates"]==c["value_records"]
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    wanted={}
    if name=="fixture":
        for j in range(4):
            wanted[(TOP+".counter_q",j,0,64)]=0
            wanted[(TOP+".index_lut",j,0,5)]=j
            wanted[(TOP+".event_q",j,16 if j==3 else 0,16 if j==3 else 32)]=0
    else:
        p="cv32e40p_alu.ff_one_i." if name=="alu" else "cv32e40p_core.ex_stage_i.alu_i.ff_one_i."
        for j in range(32):
            wanted[(p+"index_lut",j,0,5)]=j
        if name=="alu":
            assert {r["flat_assignment_id"] for r in result["items"]}==set(range(78,110))
        else:
            assert {r["flat_assignment_id"] for r in result["items"]}=={*range(138,167),*range(279,311),314,*range(400,432)}
            p="cv32e40p_core.cs_registers_i."
            for j in (1,*range(4,32)):
                wanted[(p+"mhpmcounter_q",j,0,64)]=0
            for j in range(32):
                wanted[(p+"mhpmevent_q",j,16 if j==3 else 0,16 if j==3 else 32)]=0
    observed=set()
    for row in result["items"]:
        if row["coverage"]=="partial":
            assert name=="core" and row["flat_assignment_id"]==314
            assert row["reason"]=="not_explicit_unsigned_integral_type"
            continue
        x=row["candidate"];dst=x["target"];bits=dst["bits_lsb_first"]
        assert len(dst["outer_packed_indices"])==1
        key=(dst["signal"],dst["outer_packed_indices"][0],bits[0],len(bits))
        assert key in wanted and key not in observed
        observed.add(key)
        assert bits==list(range(key[2],key[2]+key[3]))
        v=wanted[key]
        assert x["value"]==v and x["values_lsb_first"]==[int(b) for b in f"{v:0{len(bits)}b}"[::-1]]
        assert x["family"]==("lexical_unsigned_index" if key[0].endswith(".index_lut") else "literal_zero")
        assert x["potential_pairs"]==0 and x["permanent_constant"]=="not_inferred"
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
        result=audit_constant_conversions(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".constant-conversions.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"input_sha256":before,"detail_file":detail.name,
             "detail_sha256":file_sha(detail),"audit_seconds":elapsed,"upstream":upstream,
             "historical_unchanged":True,**{k:v for k,v in result.items() if k not in ("items",)}})
        save()
    try:
        extract_fixture(run/"fixture")
        case("fixture",run/"fixture")
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.constant_conversions_pr115",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":4,"word_checks_per_vector":12,
            "total_checks":48,"source_sha256":file_sha(FIXTURE)}
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
