"""Validate logical member references and partial RHS concat positions."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.member_expressions import audit_member_expressions
from rtlprep.packed_members import audit_members
from rtlprep.member_writes import audit_writes
from rtlprep.enum_member_writes import audit_enum_writes
from rtlprep.local_packed_members import audit_local_members
from scripts.run_local_packed_members_pr82 import check_core as check_pr82
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="member_expr_pr83"
FIXTURE=ROOT/"tests/fixtures/member_expr_pr83.sv"


def key(e):
    return (e["source"],e["source_bit"],e["target"],e["target_bit"],e["relation"])


def check_fixture(result):
    assert result["counts"]=={"sites":2,"supported":1,"partial_with_positions":1,
        "partial_without_positions":0,"edges":6,"logical_references":3,"concat_positions":3},result["counts"]
    assert {key(e) for e in result["edges"]}=={
        *((TOP+".bundle",i,TOP+".flag",0,"logical_member_reference_candidate") for i in range(3)),
        *((TOP+".bundle",s,TOP+".readback",t,"concat_member_position_candidate") for s,t in ((0,0),(1,1),(2,4)))}
    partial=next(r for r in result["items"] if r["coverage"]=="partial_positions")
    assert partial["unmodeled_operands"]==[{"kind":"NamedValue","target_bits":[2,3]}]


def check_core(result,old,writes,enums,local):
    check_pr82(local,old,writes,enums)
    p="cv32e40p_core.cs_registers_i."
    assert result["counts"]=={"sites":4,"supported":2,"partial_with_positions":1,
        "partial_without_positions":1,"edges":13,"logical_references":6,"concat_positions":7},result["counts"]
    rows={r["site_id"]:r for r in result["items"]}
    assert all(r["instance"]==p[:-1] for r in rows.values())
    assert {r["source"]["line"]:r["coverage"] for r in rows.values()}=={
        467:"partial_positions",1104:"expression_candidates",1105:"expression_candidates",1223:"partial"}
    expected=set()
    for line,field,target in ((1104,5,"m_irq_enable_o"),(1105,6,"u_irq_enable_o")):
        for source,bit in (("mstatus_q",field),("dcsr_q",2),("dcsr_q",11)):
            expected.add((line,(p+source,bit,p+target,0,"logical_member_reference_candidate")))
    for s,t in ((6,0),(5,3),(4,4),(3,7),(1,11),(2,12),(0,17)):
        expected.add((467,(p+"mstatus_q",s,p+"csr_rdata_int",t,"concat_member_position_candidate")))
    assert {(rows[e["site_id"]]["source"]["line"],key(e)) for e in result["edges"]}==expected
    concat=next(r for r in rows.values() if r["source"]["line"]==467)
    covered={e["target_bit"] for e in result["edges"] if e["site_id"]==concat["site_id"]}
    gaps=[b for g in concat["unmodeled_operands"] for b in g["target_bits"]]
    assert len(gaps)==25 and set(gaps)==set(range(32))-covered
    previous={r["source"]["line"] for rep in (old,writes,enums,local) for r in rep["items"] if r["coverage"]!="partial"}
    assert len(previous)==26 and not previous.intersection(r["source"]["line"] for r in rows.values())


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_expressions.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("items","edges","constants")} for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result=audit_member_expressions(read_ast(run/"fixture/elaborated_ast.json"),idx)
        report["cases"].append({"name":"fixture",**result})
        save()
        check_fixture(result)
        c,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.member_expr_pr83",run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors":32,"checks":64}
        save()
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),("core",Path(ref["core_reference_report"]).parent/"static")):
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result=audit_member_expressions(ast,idx)
            old,writes,enums,local=audit_members(ast,idx),audit_writes(ast,idx),audit_enum_writes(ast,idx),audit_local_members(ast,idx)
            report["cases"].append({"name":name,"historical_bit_counts":graph["bit_dependency_graph"]["counts"],
                "prior_member_counts":old["counts"],"prior_write_counts":writes["counts"],
                "prior_enum_counts":enums["counts"],"prior_local_counts":local["counts"],**result})
            save()
            if name=="core":
                check_core(result,old,writes,enums,local)
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
