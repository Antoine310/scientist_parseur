"""Validate configuration-specific conditional lanes and partition of CSR positions."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.member_expressions import audit_member_expressions
from rtlprep.member_patterns import audit_patterns
from rtlprep.conditional_member_concat import audit_conditional_concat
from rtlprep.packed_members import audit_members
from rtlprep.member_writes import audit_writes
from rtlprep.enum_member_writes import audit_enum_writes
from rtlprep.local_packed_members import audit_local_members
from scripts.run_member_patterns_pr84 import check_core as check_pr84
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="member_cond_pr85"
FIXTURE=ROOT/"tests/fixtures/member_cond_pr85.sv"


def check_fixture(result):
    assert result["counts"]=={"sites":2,"conditional_sites_resolved":1,"partial_sites":1,
        "conditional_operands":2,"resolved_operands":1,"constants":2,"edges":0},result
    assert {(c["target"],c["target_bit"],c["value"]) for c in result["constants"]}=={
        (TOP+".disabled_o",2,0),(TOP+".disabled_o",3,0)}
    partial=next(r for r in result["items"] if r["coverage"]=="partial")
    assert partial["conditional_operands"][0]["reason"] in ("unproven_enum_reference","selected_branch_not_proven_constant")


def check_core(result,old,writes,enums,local,expr,patterns):
    check_pr84(patterns,old,writes,enums,local,expr)
    p="cv32e40p_core.cs_registers_i."
    assert result["counts"]=={"sites":1,"conditional_sites_resolved":1,"partial_sites":0,
        "conditional_operands":2,"resolved_operands":2,"constants":3,"edges":0},result
    row=result["items"][0]
    assert row["instance"]==p[:-1] and row["source"]["line"]==467
    assert {(c["target"],c["target_bit"],c["value"]) for c in result["constants"]}=={
        (p+"csr_rdata_int",b,0) for b in (13,14,31)}
    for o in row["conditional_operands"]:
        proof=o["proof"]
        assert proof["guard_value"]==0 and proof["selected_branch"]=="right"
        assert {(x["instance"],x["name"],x["value"]) for x in proof["parameters"]}=={
            (owner,n,0) for owner in ("cv32e40p_core",p[:-1]) for n in ("FPU","ZFINX")}
    sets=[{e["target_bit"] for e in expr["edges"] if e["relation"]=="concat_member_position_candidate"},
          {c["target_bit"] for c in patterns["constants"] if c["relation"]=="concat_literal_position_candidate"},
          {c["target_bit"] for c in result["constants"]}]
    assert list(map(len,sets))==[7,22,3]
    assert not any(sets[i]&sets[j] for i,j in ((0,1),(0,2),(1,2)))
    assert set.union(*sets)==set(range(32))


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"conditional_member_concat.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("items","edges","constants")} for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result=audit_conditional_concat(read_ast(run/"fixture/elaborated_ast.json"),idx)
        report["cases"].append({"name":"fixture",**result})
        save()
        check_fixture(result)
        c,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.member_cond_pr85",run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors":8,"checks":16}
        save()
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),("core",Path(ref["core_reference_report"]).parent/"static")):
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result=audit_conditional_concat(ast,idx)
            patterns=audit_patterns(ast,idx)
            expr=audit_member_expressions(ast,idx)
            old,writes,enums,local=audit_members(ast,idx),audit_writes(ast,idx),audit_enum_writes(ast,idx),audit_local_members(ast,idx)
            report["cases"].append({"name":name,"historical_bit_counts":graph["bit_dependency_graph"]["counts"],
                "prior_member_counts":old["counts"],"prior_write_counts":writes["counts"],
                "prior_enum_counts":enums["counts"],"prior_local_counts":local["counts"],**result})
            save()
            if name=="core":
                check_core(result,old,writes,enums,local,expr,patterns)
            else:
                assert not any(result["counts"].values())
            assert not graph["analysis_limits"]["truncated_analyzers"]
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(f"Summary: {summary}",flush=True)
        print(summary.read_text(),flush=True)
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--reference",type=Path,help="Fresh diagnostics.result.json from same validated checkout")
    args=p.parse_args()
    execute(args.out,args.reference)
