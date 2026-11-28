"""Independent arithmetic range oracle, real slang and binary simulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.arithmetic_range_candidates import audit_arithmetic_range
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="arithmetic_range_pr125"
FIXTURE=ROOT/"tests/fixtures/arithmetic_range_pr125.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected=(0,0,0,0,0) if name=="alu" else (4,4,0,16,16)
    assert tuple(c[k] for k in ("roots","supported","partial","potential_pairs","stored_coordinates"))==expected,c
    assert len(result["items"])==c["roots"]
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"] and not result["partial_reasons"]
    # Independent source-line oracle; the order of historical flat IDs is not source order.
    spec={13:("fflags_n",4,0,17),14:("frm_n",2,0,19),16:("fflags_n",4,0,18),
          17:("frm_n",7,5,20)} if name=="fixture" else {
          925:("fflags_n",4,0,17),934:("frm_n",2,0,19),943:("fflags_n",4,0,18),944:("frm_n",7,5,20)}
    seen=set(); ids=set()
    for row in result["items"]:
        i=row["flat_assignment_id"]; owner=row["instance"]; line=row["source"]["line"]
        assert type(i) is int and i not in ids and line in spec and line not in seen
        ids.add(i); seen.add(line)
        dest,hi,lo,expected_id=spec[line]; n=hi-lo+1
        assert row["historical_status"]=="captured" and row["context"]=="AlwaysComb"
        assert owner==(TOP if name=="fixture" else "cv32e40p_core.cs_registers_i")
        if name=="core":
            assert i==expected_id and row["historical_residual"] and row["matched_historical_edges"]==0
        dst=owner+"."+dest; src=owner+".csr_wdata_int"; x=row["candidate"]
        assert x["target"]==dst and x["source"]==src
        assert x["model"]=={"msb":hi,"lsb":lo,"width":n,"source_width":32,
                            "domain":"defined_binary_inputs_only"}
        def param(p,v): return {"kind":"localparam","type":"logic signed[31:0]","parameter":p,"value":v}
        def lit(v): return {"kind":"literal","type":"int","value":v}
        def op(k,a,b,v): return {"kind":k,"type":"logic signed[31:0]","left":a,"right":b,"value":v}
        flags=param("C_FFLAG",5); rm=param("C_RM",3)
        upper=flags if dest=="fflags_n" else rm if lo==0 else op("Add",rm,flags,8)
        lower=flags if lo else lit(0)
        one={"kind":"conversion","type":"logic signed[31:0]","operand":lit(1),"value":1}
        assert x["bound_proofs"]=={"msb":op("Subtract",upper,one,hi),"lsb":lower}
        params=[("C_FFLAG",5)] if dest=="fflags_n" else [("C_RM",3)] if lo==0 else [("C_RM",3),("C_FFLAG",5)]
        assert x["parameter_proofs"]==[{"instance":owner,"parameter":p,"value":v,
                                      "method":"direct_typed_literal_localparam"} for p,v in params]
        assert x["pairs"]==[{"source":src,"source_bit":lo+b,"target":dst,"target_bit":b} for b in range(n)]
        assert x["potential_pairs"]==n and x["permanent_constant"]=="not_inferred"
    assert seen==(set() if name=="alu" else set(spec))
    if name=="core":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"],
                c["matched_historical_edges"],c["residual_candidate_pairs"])==(3811,1199,4,0,16)
    elif name=="alu":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(612,479,0)
    else:
        # Fixture support classification is measured, not forced by changing the history.
        assert c["matched_historical_edges"]+c["residual_candidate_pairs"]<=16


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
        result=audit_arithmetic_range(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".arithmetic-range.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.arithmetic_range_pr125",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":51200,"word_checks_per_vector":2,
            "total_checks":102400,"source_sha256":file_sha(FIXTURE)}
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
