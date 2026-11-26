"""Validate NBA patterns and literal lanes against independent oracles."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.member_expressions import audit_member_expressions
from rtlprep.member_patterns import audit_patterns
from rtlprep.packed_members import audit_members
from rtlprep.member_writes import audit_writes
from rtlprep.enum_member_writes import audit_enum_writes
from rtlprep.local_packed_members import audit_local_members
from scripts.run_member_expressions_pr83 import check_core as check_pr83
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="member_pattern_pr84"
FIXTURE=ROOT/"tests/fixtures/member_pattern_pr84.sv"


def check_fixture(result):
    assert result["counts"]=={"sites":2,"nba_sites":1,"concat_partial_sites":1,"unmodeled_sites":0,
                              "nba_sampled_edges":2,"nba_constants":3,"concat_constants":2},result["counts"]
    assert {(e["source"],e["source_bit"],e["target"],e["target_bit"]) for e in result["edges"]}=={
        (TOP+".d",4,TOP+".q",4),(TOP+".d",3,TOP+".q",3)}
    assert {(c["target"],c["target_bit"],c["value"]) for c in result["constants"]}=={
        (TOP+".q",0,0),(TOP+".q",1,0),(TOP+".q",2,1),
        (TOP+".readback",5,0),(TOP+".readback",6,0)}


def check_core(result,old,writes,enums,local,expr):
    check_pr83(expr,old,writes,enums,local)
    p="cv32e40p_core.cs_registers_i."
    assert result["counts"]=={"sites":2,"nba_sites":1,"concat_partial_sites":1,"unmodeled_sites":0,
                              "nba_sampled_edges":2,"nba_constants":5,"concat_constants":22},result["counts"]
    rows={r["site_id"]:r for r in result["items"]}
    assert all(r["instance"]==p[:-1] for r in rows.values())
    assert {r["source"]["line"]:r["coverage"] for r in rows.values()}=={
        467:"partial_literal_positions",1223:"nba_assignment_candidates"}
    assert {(rows[e["site_id"]]["source"]["line"],e["source"],e["source_bit"],e["target"],e["target_bit"])
            for e in result["edges"]}=={(1223,p+"mstatus_n",b,p+"mstatus_q",b) for b in (3,5)}
    zero_bits={1,2,5,6,8,9,10,15,16,*range(18,31)}
    expected={(467,p+"csr_rdata_int",b,0) for b in zero_bits}
    expected.update((1223,p+"mstatus_q",b,v) for b,v in ((0,0),(1,1),(2,1),(4,0),(6,0)))
    assert {(rows[c["site_id"]]["source"]["line"],c["target"],c["target_bit"],c["value"])
            for c in result["constants"]}==expected
    prior_positions={e["target_bit"] for e in expr["edges"] if e["relation"]=="concat_member_position_candidate"}
    assert not prior_positions.intersection(zero_bits)
    assert set(range(32))-prior_positions-zero_bits=={13,14,31}


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_patterns.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("items","edges","constants")} for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result=audit_patterns(read_ast(run/"fixture/elaborated_ast.json"),idx)
        report["cases"].append({"name":"fixture",**result})
        save()
        check_fixture(result)
        c,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.member_pattern_pr84",run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors":32,"checks":65}
        save()
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),("core",Path(ref["core_reference_report"]).parent/"static")):
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result=audit_patterns(ast,idx)
            expr=audit_member_expressions(ast,idx)
            old,writes,enums,local=audit_members(ast,idx),audit_writes(ast,idx),audit_enum_writes(ast,idx),audit_local_members(ast,idx)
            report["cases"].append({"name":name,"historical_bit_counts":graph["bit_dependency_graph"]["counts"],
                "prior_member_counts":old["counts"],"prior_write_counts":writes["counts"],
                "prior_enum_counts":enums["counts"],"prior_local_counts":local["counts"],**result})
            save()
            if name=="core":
                check_core(result,old,writes,enums,local,expr)
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
