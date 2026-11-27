"""Independent coordinate oracle for real slang controlled signed order candidates."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.comparison_candidates import audit_comparisons
from rtlprep.signed_order_candidates import audit_signed_order
from scripts.run_comparison_pr100 import check as check_pr100
from rtlprep.residual_audit import audit_residuals
from rtlprep.zero_extended_additions import audit_zero_extended_additions
from rtlprep.constant_increments import audit_increments
from rtlprep.subtraction_candidates import audit_subtractions
from scripts.run_zero_extended_addition_pr97 import check as check_pr97
from scripts.run_constant_increments_pr98 import check as check_pr98
from scripts.run_subtraction_pr99 import check as check_pr99
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_benchmark_pr91 import file_hash,digest
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="signed_order_pr101"
FIXTURE=ROOT/"tests/fixtures/signed_order_pr101.sv"


def check(result,name):
    c=result["counts"]
    expected={"fixture":(1,1,17,18),"alu":(4,4,68,72),"core":(4,4,68,72)}[name]
    assert (c["roots"],c["supported"],c["potential_pairs"],c["stored_coordinates"])==expected,c
    assert not c["partial"] and not c["truncated"]
    actual={}
    for row in result["items"]:
        assert row["coverage"]=="signed_order_candidates"
        x=row["candidate"]; dst=x["target"]
        assert dst["signal"]==row["target"] and not dst["outer_packed_indices"]
        key=(dst["signal"],tuple(dst["bits_lsb_first"]))
        assert key not in actual
        assert x["operator"]=="GreaterThan" and x["operand_width"]==8
        assert x["operand_roles"]==["left_data","right_data","shared_sign_control"]
        assert x["potential_pairs"]==17 and x["shared_control_occurrences"]==2
        assert all(not e["outer_packed_indices"] for e in x["operands"])
        actual[key]=[(e["signal"],tuple(e["bits_lsb_first"])) for e in x["operands"]]
        assert [(e["signal"],tuple(e["bits_lsb_first"])) for e in x["sign_msb_evidence"]]==[
            (signal,(bits[-1],)) for signal,bits in actual[key][:2]]
    expected={}
    if name=="fixture":
        prefix=TOP+"."
        expected[(prefix+"greater",(0,))]=[(prefix+"a",tuple(range(8))),(prefix+"b",tuple(range(8))),(prefix+"mode",(0,))]
    else:
        prefix="cv32e40p_alu." if name=="alu" else "cv32e40p_core.ex_stage_i.alu_i."
        for i in range(4):
            bits=tuple(range(8*i,8*i+8))
            expected[(prefix+"is_greater_vec",(i,))]=[(prefix+"operand_a_i",bits),(prefix+"operand_b_i",bits),(prefix+"cmp_signed",(i,))]
    assert actual==expected,(actual,expected)


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
        result=audit_signed_order(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".signed-order.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        assert result["counts"]["residual_ids"]==expected_residual,result["counts"]
        check(result,name)
        census=audit_residuals(ast,idx,g)
        roots={r["assignment_id"] for r in census["rows"] if r["rhs_syntax"]["root_operator"]=="GreaterThan"}
        all_ids={r["assignment_id"] for r in census["rows"] if "BinaryOp:GreaterThan" in r["rhs_syntax"]["operators"]}
        assert all_ids==roots and {r["flat_assignment_id"] for r in result["items"]}==roots
        good={r["flat_assignment_id"] for r in result["items"] if r["coverage"]=="signed_order_candidates"}
        union=None
        if name!="fixture":
            z=audit_zero_extended_additions(ast,idx,g)
            inc=audit_increments(ast,idx,g)
            sub=audit_subtractions(ast,idx,g)
            eq=audit_comparisons(ast,idx,g)
            check_pr97(z,name);check_pr98(inc,name);check_pr99(sub,name);check_pr100(eq,name)
            old={r["flat_assignment_id"] for x in (z,inc,sub,eq) for r in x["items"] if r["coverage"]!="partial"}
            assert len(old)==(35 if name=="alu" else 72) and not old&good
            union={"previous_characterized_ids":len(old),"signed_order_ids":len(good),
                   "unique_characterized_residual_ids":len(old|good),
                   "remaining_residual_ids":expected_residual-len(old|good),
                   "historical_graph_promoted":False}
        assert digest(g)==before and hashes=={f:file_hash(folder/f) for f in files}
        report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
            "historical_unchanged":True,"detail_file":detail.name,"union":union,
            "greater_than_operator_rows":len(all_ids),"nested_greater_than_rows_not_promoted":len(all_ids-roots),
            **{k:v for k,v in result.items() if k!="items"}})
        save()
    try:
        extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture",1)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.signed_order_pr101",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","checks":131072,"source_sha256":file_hash(FIXTURE)}
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
