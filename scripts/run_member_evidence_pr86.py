"""Recompute all seven member audits on one AST/index; check lossless envelope."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.member_evidence import collect
from scripts.run_conditional_member_concat_pr85 import check_core as check_pr85
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="member_cond_pr85"
FIXTURE=ROOT/"tests/fixtures/member_cond_pr85.sv"

def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def check_lossless(result,reports):
    rows={r["row_id"]:r for r in result["rows"]}
    assert len(rows)==len(result["rows"])
    assert len({r["record_id"] for r in result["records"]})==len(result["records"])
    for p in result["producers"]:
        name=p["producer"]
        restored={**p["metadata"],"items":[r["payload"] for r in result["rows"] if r["producer"]==name]}
        for k in p["present_collections"]:
            restored[k]=[r["payload"] for r in result["records"] if r["producer"]==name and r["collection"]==k]
        assert restored==reports[name]
    for r in result["records"]:
        assert rows[r["row_id"]]["producer"]==r["producer"]
        assert rows[r["row_id"]]["payload"]["site_id"]==r["payload"]["site_id"]

def check_core(result,reports):
    check_pr85(reports["pr85"],reports["pr79"],reports["pr80"],reports["pr81"],
               reports["pr82"],reports["pr83"],reports["pr84"])
    assert result["counts"]=={"producer_reports":7,"producer_rows":56,"candidate_records":1481,
        "position":660,"logical_reference":6,"nba_sampled":2,"local_constant":805,
        "nba_constant":5,"configuration_constant":3},result["counts"]
    assert len([r for r in result["rows"] if r["producer"]=="pr79"])==30

def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_evidence.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("rows","records","producers")} for c in report["cases"]]},indent=2),encoding="utf-8")
    def case(name,folder,idx):
        ast_path=folder/"elaborated_ast.json"
        result,reports=collect(read_ast(ast_path),idx)
        check_lossless(result,reports)
        report["cases"].append({"name":name,"ast_sha256":sha256(ast_path),
            "index_sha256":sha256(folder/"rtl_index.json"),**result})
        save()
        return result,reports
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result,reports=case("fixture",run/"fixture",idx)
        assert result["counts"]["position"]==4 and result["counts"]["configuration_constant"]==2
        assert result["counts"]["candidate_records"]==6
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),
                            ("core",Path(ref["core_reference_report"]).parent/"static")):
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result,reports=case(name,folder,idx)
            if name=="core":
                check_core(result,reports)
            else:
                assert result["counts"]["producer_rows"]==result["counts"]["candidate_records"]==0
            assert not graph["analysis_limits"]["truncated_analyzers"]
            report["cases"][-1]["historical_bit_counts"]=graph["bit_dependency_graph"]["counts"]
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
