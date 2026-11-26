"""Fixture and pinned CSR oracle for scalar member writes."""
import argparse
import json
from pathlib import Path
import tempfile
from rtlprep.analysis_budgets import read_ast
from rtlprep.member_writes import audit_writes
from rtlprep.packed_members import audit_members
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT = Path(__file__).resolve().parents[1]
TOP = "member_pr80"
FIXTURE = ROOT / "tests/fixtures/member_pr80.sv"

def edge_key(e):
    return e["source"], e["source_bit"], e["target"], e["target_bit"]

def const_key(c):
    return c["target"], c["target_bit"], c["value"]

def check_fixture(result):
    assert result["counts"] == {"sites":4,"supported":4,"partial":0,"edges":2,"constants":2}, result
    assert {edge_key(e) for e in result["edges"]} == {
        (TOP+".data",3,TOP+".bundle",3), (TOP+".data",1,TOP+".bundle",1)}
    assert {const_key(c) for c in result["constants"]} == {
        (TOP+".bundle",2,0), (TOP+".bundle",0,1)}

def check_core(result, old):
    p = "cv32e40p_core.cs_registers_i."
    expected_edges = {999: (p+"csr_wdata_int",15,p+"dcsr_n",15),
                      1002:(p+"csr_wdata_int",11,p+"dcsr_n",11),
                      1006:(p+"csr_wdata_int",2,p+"dcsr_n",2)}
    expected_constants = {1000:(p+"dcsr_n",13,0),1001:(p+"dcsr_n",12,0),
                          1003:(p+"dcsr_n",10,0),1004:(p+"dcsr_n",9,0),
                          1005:(p+"dcsr_n",4,0),1060:(p+"mstatus_n",5,0),
                          1070:(p+"mstatus_n",3,1)}
    rows = {r["site_id"]:r for r in result["items"]}
    assert result["counts"]["supported"] == 10 and result["counts"]["edges"] == 3 and result["counts"]["constants"] == 7, result
    assert {rows[e["site_id"]]["source"]["line"]:edge_key(e) for e in result["edges"]} == expected_edges
    assert {rows[c["site_id"]]["source"]["line"]:const_key(c) for c in result["constants"]} == expected_constants
    assert all(r["instance"] == p[:-1] for r in rows.values() if r["coverage"] != "partial")
    assert old["counts"] == {"sites":30,"supported":7,"partial":23,"edges":10}
    old_lines = {r["source"]["line"] for r in old["items"] if r["coverage"] == "position_candidates"}
    assert not old_lines.intersection(set(expected_edges) | set(expected_constants))

def execute(out):
    out = out.resolve()
    for entry in load_lock():
        root = (ROOT / entry["destination"]).resolve()
        if out == root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=out))
    path, summary = run/"member_writes.result.json", run/"summary.json"
    report = {"status":"incomplete","cases":[],"design_coverage":"not_measured",
              "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("items","edges","constants")} for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result=audit_writes(read_ast(run/"fixture/elaborated_ast.json"),idx)
        report["cases"].append({"name":"fixture",**result})
        save()
        check_fixture(result)
        c,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.member_pr80",run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors":16,"checks":16}
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,folder in (("alu",d.parent/"alu"),
                           ("core",Path(ref["core_reference_report"]).parent/"static")):
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result=audit_writes(ast,idx)
            old=audit_members(ast,idx)
            report["cases"].append({"name":name,"prior_member_counts":old["counts"],
                                    "historical_bit_counts":graph["bit_dependency_graph"]["counts"],**result})
            save()
            if name=="core":
                check_core(result,old)
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
    execute(p.parse_args().out)
