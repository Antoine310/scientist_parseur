"""Frozen coordinate oracle for CSR and aligned prefetch address increments."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.constant_increments import audit_increments
from rtlprep.zero_extended_additions import audit_zero_extended_additions
from scripts.run_zero_extended_addition_pr97 import check as check_pr97
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_benchmark_pr91 import file_hash,digest
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="increment_pr98"
FIXTURE=ROOT/"tests/fixtures/increment_pr98.sv"

def signature(c):
    dst,src=c["target"],c["operands"][0]
    return (dst["signal"],tuple(dst["outer_packed_indices"]),tuple(dst["bits_lsb_first"]),
            src["signal"],tuple(src["outer_packed_indices"]),tuple(src["bits_lsb_first"]),
            c["constant_addend"],c["low_zero_input_bits"],tuple(c["prefix_lengths"]))

def expected_row(dst,src,n,outer=(),shift=0):
    return (dst,outer,tuple(range(n)),src,outer,tuple(range(shift,n)),1<<shift,shift,
            tuple(max(0,i-shift+1) for i in range(n)))

def check(result,name):
    good=[r for r in result["items"] if r["coverage"]=="addition_candidates"]
    expected=set()
    if name=="core":
        p="cv32e40p_core.cs_registers_i."
        expected={expected_row(p+"mhpmcounter_increment",p+"mhpmcounter_q",64,(i,)) for i in range(32)}
        p="cv32e40p_core.if_stage_i.prefetch_buffer_i.prefetch_controller_i."
        expected.add(expected_row(p+"trans_addr_incr",p+"trans_addr_q",32,shift=2))
    elif name=="fixture":
        expected={expected_row(TOP+".small_next",TOP+".a",4),
                  expected_row(TOP+".counter_next",TOP+".counter",64),
                  expected_row(TOP+".address_next",TOP+".address",32,shift=2)}
    assert {signature(r["candidate"]) for r in good}==expected and len(good)==len(expected)
    for r in good:
        c=r["candidate"]
        assert c["potential_pairs"]==sum(c["prefix_lengths"])
        assert c["constant_result_positions"]==([{"bit":0,"value":0},{"bit":1,"value":0}]
                                                if c["low_zero_input_bits"] else [])
    expected_counts={"fixture":(3,3,2555,198),"alu":(31,0,0,0),"core":(64,33,67025,4158)}[name]
    c=result["counts"]
    assert (c["roots"],c["supported"],c["potential_pairs"],c["stored_coordinates"])==expected_counts,c
    assert c["partial"]==c["roots"]-c["supported"] and not c["truncated"]

def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed_in_this_runner"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,expected_residual):
        files=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
        hashes={f:file_hash(folder/f) for f in files}
        ast=read_ast(folder/files[0])
        idx=json.loads((folder/files[1]).read_text())
        g=json.loads((folder/files[2]).read_text())
        before=digest(g)
        start=perf_counter()
        result=audit_increments(ast,idx,g)
        elapsed=perf_counter()-start
        assert result["counts"]["residual_ids"]==expected_residual
        check(result,name)
        union=None
        if name!="fixture":
            previous=audit_zero_extended_additions(ast,idx,g)
            check_pr97(previous,name)
            assert [r["flat_assignment_id"] for r in previous["items"]]==[r["flat_assignment_id"] for r in result["items"]]
            prior={r["flat_assignment_id"] for r in previous["items"] if r["coverage"]=="addition_candidates"}
            new={r["flat_assignment_id"] for r in result["items"] if r["coverage"]=="addition_candidates"}
            roots={r["flat_assignment_id"] for r in result["items"]}
            assert not prior&new and prior|new==roots
            union={"pr97":len(prior),"pr98":len(new),"unique_addition_roots":len(prior|new),
                   "remaining_addition_roots":0,"historical_graph_promoted":False}
        assert digest(g)==before and hashes=={f:file_hash(folder/f) for f in files}
        detail=run/(name+".increments.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
            "historical_unchanged":True,"detail_file":detail.name,"addition_union":union,
            **{k:v for k,v in result.items() if k!="items"}})
        save()
    try:
        extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture",3)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.increment_pr98",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","checks":32,"source_sha256":file_hash(FIXTURE)}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu",98)
        case("core",Path(d["core_reference_report"]).parent/"static",384)
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
    args=p.parse_args()
    execute(args.out,args.reference)
