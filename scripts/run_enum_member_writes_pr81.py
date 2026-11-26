"""Validate enum member writes against a real fixture and pinned CSR sites."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.enum_member_writes import audit_enum_writes
from rtlprep.member_writes import audit_writes
from rtlprep.packed_members import audit_members
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_writes_pr80 import check_core as check_pr80
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="enum_members_pr81"
FIXTURE=ROOT/"tests/fixtures/enum_members_pr81.sv"


def check_fixture(result):
    assert result["counts"]=={"sites":2,"supported":2,"partial":0,"edges":0,"constants":4}, result
    assert {(c["enum_value"],c["target"],c["target_bit"],c["value"]) for c in result["constants"]} == {
        ("LO",TOP+".bundle",1,1),("LO",TOP+".bundle",2,0),
        ("HI",TOP+".bundle",1,0),("HI",TOP+".bundle",2,1)}


def check_core(result, old, writes):
    check_pr80(writes,old)
    p="cv32e40p_core.cs_registers_i."
    expected={1007:(p+"dcsr_n",(0,1)),1054:(p+"dcsr_n",(0,1)),
              1061:(p+"mstatus_n",(1,2)),1071:(p+"mstatus_n",(1,2))}
    assert result["counts"]=={"sites":4,"supported":4,"partial":0,"edges":0,"constants":8}, result
    rows={r["site_id"]:r for r in result["items"]}
    actual={(rows[c["site_id"]]["source"]["line"],c["target"],c["target_bit"],c["value"],c["enum_value"])
            for c in result["constants"]}
    assert actual=={(line,target,bit,1,"PRIV_LVL_M") for line,(target,bits) in expected.items() for bit in bits}
    assert all(r["instance"]==p[:-1] for r in rows.values())
    previous={r["source"]["line"] for report in (old,writes) for r in report["items"] if r["coverage"]!="partial"}
    assert not previous.intersection(expected) and len(previous)==17


def execute(out, reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"enum_member_writes.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("items","edges","constants")} for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result=audit_enum_writes(read_ast(run/"fixture/elaborated_ast.json"),idx)
        report["cases"].append({"name":"fixture",**result})
        save()
        check_fixture(result)
        c,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.enum_members_pr81",run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors":4,"checks":4}
        save()
        # Reuse fresh PR80 extraction in the same CI job; local default regenerates.
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),
                            ("core",Path(ref["core_reference_report"]).parent/"static")):
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result=audit_enum_writes(ast,idx)
            old,writes=audit_members(ast,idx),audit_writes(ast,idx)
            report["cases"].append({"name":name,"historical_bit_counts":graph["bit_dependency_graph"]["counts"],
                                    "prior_member_counts":old["counts"],"prior_write_counts":writes["counts"],**result})
            save()
            if name=="core":
                check_core(result,old,writes)
            else:
                assert result["counts"]=={"sites":0,"supported":0,"partial":0,"edges":0,"constants":0}
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
