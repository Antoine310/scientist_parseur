"""Frozen residual subtraction oracle with real slang and fixture simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.subtraction_candidates import audit_subtractions
from rtlprep.residual_audit import audit_residuals
from rtlprep.zero_extended_additions import audit_zero_extended_additions
from rtlprep.constant_increments import audit_increments
from scripts.run_zero_extended_addition_pr97 import check as check_pr97
from scripts.run_constant_increments_pr98 import check as check_pr98
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_benchmark_pr91 import file_hash,digest
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="subtraction_pr99"
FIXTURE=ROOT/"tests/fixtures/subtraction_pr99.sv"


def check(result,name):
    good=[r for r in result["items"] if r["coverage"]=="subtraction_candidates"]
    c=result["counts"]
    expected={"fixture":(2,2,135,43),"alu":(0,0,0,0),"core":(2,2,135,43)}[name]
    assert (c["roots"],c["supported"],c["potential_pairs"],c["stored_coordinates"])==expected,c
    assert c["partial"]==0 and not c["truncated"]
    if name=="alu":
        return
    if name=="fixture":
        delta,mask=TOP+".delta",TOP+".mask"
        a,b,k=TOP+".a",TOP+".b",TOP+".instr"
        shift=2
    else:
        p="cv32e40p_core.load_store_unit_i."
        delta,a,b=p+"wdata_offset",p+"data_addr_int",p+"data_reg_offset_ex_i"
        p="cv32e40p_core.id_stage_i."
        mask,k=p+"imm_clip_type",p+"instr"
        shift=20
    rows={r["target"]:r["candidate"] for r in good}
    assert set(rows)=={delta,mask} and len(rows)==len(good)
    for target,n,sources in ((delta,2,[(a,range(2)),(b,range(2))]),
                            (mask,32,[(k,range(shift,shift+5))])):
        item=rows[target]
        assert item["target"]["signal"]==target and item["target"]["bits_lsb_first"]==list(range(n))
        assert item["target"]["outer_packed_indices"]==[]
        assert [(e["signal"],e["outer_packed_indices"],e["bits_lsb_first"]) for e in item["operands"]]==[
            (s,[],list(bits)) for s,bits in sources]
    assert rows[delta]["prefix_lengths"]==[1,2] and rows[delta]["potential_pairs"]==6
    assert rows[delta]["constant_result_positions"]==[]
    # Independent exhaustive binary oracle, not the analyzer's threshold formula.
    expected_pairs={(j,i) for k in range(32) for j in range(5) for i in range(32)
                    if (((1<<k)-1)^((1<<(k^(1<<j)))-1))&(1<<i)}
    actual={(j,i) for i,offsets in enumerate(rows[mask]["source_offsets_by_result"]) for j in offsets}
    assert actual==expected_pairs and len(actual)==129==rows[mask]["potential_pairs"]
    assert rows[mask]["constant_result_positions"]==[{"bit":31,"value":0}]


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
    def case(name,folder,expected_residual,expected_nested):
        files=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
        hashes={f:file_hash(folder/f) for f in files}
        ast=read_ast(folder/files[0])
        idx=json.loads((folder/files[1]).read_text())
        g=json.loads((folder/files[2]).read_text())
        before=digest(g)
        start=perf_counter()
        result=audit_subtractions(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".subtractions.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        assert result["counts"]["residual_ids"]==expected_residual,result["counts"]
        check(result,name)
        census=audit_residuals(ast,idx,g)
        root_ids={r["assignment_id"] for r in census["rows"] if r["rhs_syntax"]["root_operator"]=="Subtract"}
        nested={r["assignment_id"] for r in census["rows"] if
                "BinaryOp:Subtract" in r["rhs_syntax"]["operators"]}-root_ids
        assert len(nested)==expected_nested and {r["flat_assignment_id"] for r in result["items"]}==root_ids
        union=None
        if name!="fixture":
            old=audit_zero_extended_additions(ast,idx,g)
            inc=audit_increments(ast,idx,g)
            check_pr97(old,name)
            check_pr98(inc,name)
            adds={r["flat_assignment_id"] for x in (old,inc) for r in x["items"] if r["coverage"]=="addition_candidates"}
            assert len(adds)==(31 if name=="alu" else 64) and not adds&root_ids
            union={"addition_roots":len(adds),"subtraction_roots":len(root_ids),
                   "unique_characterized_residual_ids":len(adds|root_ids),
                   "remaining_residual_ids":expected_residual-len(adds|root_ids),
                   "historical_graph_promoted":False}
        assert digest(g)==before and hashes=={f:file_hash(folder/f) for f in files}
        report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
            "historical_unchanged":True,"detail_file":detail.name,"arithmetic_union":union,
            "nested_subtraction_rows_not_promoted":len(nested),
            **{k:v for k,v in result.items() if k!="items"}})
        save()
    try:
        extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture",2,0)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.subtraction_pr99",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","checks":48,"source_sha256":file_hash(FIXTURE)}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu",98,0)
        case("core",Path(d["core_reference_report"]).parent/"static",384,5)
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
