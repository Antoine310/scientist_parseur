"""Independent packed lane concat oracle, real slang and binary simulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.packed_lane_concat_candidates import audit_packed_lane_concat
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="packed_lane_concat_pr121"
FIXTURE=ROOT/"tests/fixtures/packed_lane_concat_pr121.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    assert tuple(c[k] for k in ("roots","supported","partial","potential_pairs","local_value_records","stored_coordinates"))==(8,8,0,8,8,16),c
    assert len(result["items"])==c["roots"]
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"] and not result["partial_reasons"]
    # Historical bit-access traversal is not source order for this if/else.
    # Independently pinned from the fixture AST/capture in CI 46152427528.
    ids={"alu":[413,414,415,416,437,438,439,440],
         "core":[735,736,737,738,759,760,761,762],
         "fixture":[7,0,1,2,3,4,5,6]}[name]
    lines=[9,10,11,12,14,15,16,17] if name=="fixture" else [602,603,604,605,662,663,664,665]
    expected={}
    for j,i in enumerate(ids):
        k=3-(j%4)
        src="imm_vec_ext_i" if j<4 else "operand_b_i"
        b=0 if j<4 or j>=6 else 16
        v=[1,1,1,0,1,0,1,0][j]
        expected[i]=(k,src,b,v,lines[j])
    observed=set()
    for row in result["items"]:
        i=row["flat_assignment_id"]
        assert i in expected and i not in observed
        observed.add(i)
        k,src,b,v,line=expected[i]; x=row["candidate"]; owner=row["instance"]
        assert row["context"]=="AlwaysComb" and row["historical_status"]=="captured"
        assert row["historical_residual"],(name,i)
        assert owner=={"fixture":TOP,"alu":"cv32e40p_alu","core":"cv32e40p_core.ex_stage_i.alu_i"}[name],(name,i,owner)
        assert row["source"]["line"]==line,(name,i,row["source"],line)
        dst=owner+".shuffle_byte_sel"
        assert x["target"]==dst and x["outer_index"]==k,(name,i,x["target"],x["outer_index"],dst,k)
        assert x["pairs"]==[{"source":owner+"."+src,"source_packed_indices":[],"source_bit":b,
                             "target":dst,"target_packed_indices":[k],"target_bit":1}]
        assert x["local_values"]==[{"target":dst,"target_packed_indices":[k],"target_bit":0,"value":v}]
        assert x["model"]=={"outer_index":k,"dynamic_inner_bit":1,"literal_inner_bit":0,
                           "literal_value":v,"width":2,"domain":"defined_binary_inputs_only"}
        assert x["permanent_constant"]=="not_inferred"
    assert observed==set(ids)
    if name=="core":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(3811,1199,8)
    elif name=="alu":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(612,479,8)
    else:
        assert (c["ast_occurrences"],c["historical_rows"])==(8,8)


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
        result=audit_packed_lane_concat(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".packed-lane-concat.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.packed_lane_concat_pr121",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":64,"word_checks_per_vector":1,
            "total_checks":64,"source_sha256":file_sha(FIXTURE)}
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
