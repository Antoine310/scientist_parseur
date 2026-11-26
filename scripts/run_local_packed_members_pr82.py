"""Independent fixture and pinned CSR oracle for local packed members."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.local_packed_members import audit_local_members
from rtlprep.packed_members import audit_members
from rtlprep.member_writes import audit_writes
from rtlprep.enum_member_writes import audit_enum_writes
from scripts.run_enum_member_writes_pr81 import check_core as check_pr81
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="local_members_pr82"
FIXTURE=ROOT/"tests/fixtures/local_members_pr82.sv"


def edge_key(e):
    return (e["source"],e["source_bit"],e["source_field"],tuple(e["source_field_coordinates"]),
            e["target"],e["target_packed_offset"],tuple(e["target_coordinates"]))


def const_key(c):
    return (c["target"],c["target_bit"],c["field"],tuple(c["field_coordinates"]),c["value"])


def check_fixture(result):
    assert result["counts"]=={"sites":4,"supported":4,"partial":0,"edges":12,"constants":12}, result["counts"]
    expected_edges=set()
    expected_constants=set()
    for field,target,offset,coords in (
        ("upper","hi",4,[(i//4,i%4) for i in range(8)]),
        ("lower","lo",0,[(1-i//2,i%2) for i in range(4)])):
        for i,coord in enumerate(coords):
            expected_edges.add((TOP+".bundle",offset+i,field,coord,TOP+"."+target,i,coord))
            expected_constants.add((TOP+".zero_bundle",offset+i,field,coord,0))
    assert {edge_key(e) for e in result["edges"]}==expected_edges
    assert {const_key(c) for c in result["constants"]}==expected_constants


def check_core(result, old, writes, enums):
    check_pr81(enums,old,writes)
    p="cv32e40p_core.cs_registers_i."
    assert result["counts"]=={"sites":5,"supported":5,"partial":0,"edges":640,"constants":768}, result["counts"]
    rows={r["site_id"]:r for r in result["items"]}
    assert all(r["instance"]==p[:-1] for r in rows.values())
    e_expected=set()
    c_expected=set()
    for line,field,offset,n,w in ((910,"pmpaddr",256,512,32),
                                  (911,"pmpcfg_packed",128,128,32),
                                  (912,"pmpcfg",0,128,8)):
        for i in range(n):
            c_expected.add((line,(p+"pmp_reg_n",offset+i,field,(i//w,i%w),0)))
    for line,field,target,offset,n,w in ((1125,"pmpaddr","pmp_addr_o",256,512,32),
                                         (1126,"pmpcfg","pmp_cfg_o",0,128,8)):
        for i in range(n):
            coord=(i//w,i%w)
            e_expected.add((line,(p+"pmp_reg_q",offset+i,field,coord,p+target,i,coord)))
    assert {(rows[e["site_id"]]["source"]["line"],edge_key(e)) for e in result["edges"]}==e_expected
    assert {(rows[c["site_id"]]["source"]["line"],const_key(c)) for c in result["constants"]}==c_expected
    previous={r["source"]["line"] for rep in (old,writes,enums) for r in rep["items"] if r["coverage"]!="partial"}
    current={r["source"]["line"] for r in rows.values()}
    assert len(previous)==21 and len(current)==5 and not previous.intersection(current)


def execute(out, reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"local_packed_members.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("items","edges","constants")} for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result=audit_local_members(read_ast(run/"fixture/elaborated_ast.json"),idx)
        report["cases"].append({"name":"fixture",**result})
        save()
        check_fixture(result)
        c,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.local_members_pr82",run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors":4096,"checks":12288}
        save()
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),
                            ("core",Path(ref["core_reference_report"]).parent/"static")):
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result=audit_local_members(ast,idx)
            old,writes,enums=audit_members(ast,idx),audit_writes(ast,idx),audit_enum_writes(ast,idx)
            report["cases"].append({"name":name,"historical_bit_counts":graph["bit_dependency_graph"]["counts"],
                                    "prior_member_counts":old["counts"],"prior_write_counts":writes["counts"],
                                    "prior_enum_counts":enums["counts"],**result})
            save()
            if name=="core":
                check_core(result,old,writes,enums)
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
