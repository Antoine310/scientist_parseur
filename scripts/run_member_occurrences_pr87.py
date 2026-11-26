"""Validate linkage of fresh member audits to exact traversal occurrences."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.member_evidence import collect
from rtlprep.member_occurrences import collect_linked
from scripts.run_member_evidence_pr86 import check_core as check_pr86, check_lossless
from scripts.run_conditional_member_concat_pr85 import check_core as check_pr85
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="member_occ_pr87"
FIXTURE=ROOT/"tests/fixtures/member_occ_pr87.sv"

def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def check_core(result,reports,linked):
    check_pr86(result,reports)
    assert linked["counts"]=={"occurrences":30,"producer_rows":56,"candidate_records":1481,
        "distinct_exact_records":1481,"duplicate_records":0,"overlap_groups":0,
        "candidate_disagreement_groups":0,"mixed_coordinate_groups":0,"occurrences_without_records":0},linked["counts"]
    groups=linked["occurrences"]
    assert len({g["occurrence_ordinal"] for g in groups})==30
    assert {g["source"]["line"] for g in groups}=={r["source"]["line"] for r in reports["pr79"]["items"]}
    # Check the two important multi-producer partitions by exact linked record IDs.
    by_id={r["record_id"]:r for r in result["records"]}
    csr=next(g for g in groups if g["source"]["line"]==467)
    records=[by_id[rid] for rid in csr["record_ids"]]
    assert len(records)==32 and {r["payload"]["target_bit"] for r in records}==set(range(32))
    assert len(csr["row_ids"])==4
    nba=next(g for g in groups if g["source"]["line"]==1223)
    assert len(nba["record_ids"])==7 and len(nba["row_ids"])==3


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_occurrences.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("rows","records","producers","linkage")} for c in report["cases"]]},indent=2),encoding="utf-8")
    def case(name,folder,idx):
        ast_path=folder/"elaborated_ast.json"
        ast=read_ast(ast_path)
        result,reports,linked=collect_linked(ast,idx)
        check_lossless(result,reports)
        report["cases"].append({"name":name,"ast_sha256":sha256(ast_path),
            "index_sha256":sha256(folder/"rtl_index.json"),**result,
            "linkage_counts":linked["counts"],"linkage":linked})
        save()
        return result,reports,linked
    save()
    try:
        _,idx=extract(run/"fixture",TOP,[FIXTURE])
        result,reports,linked=case("fixture",run/"fixture",idx)
        assert linked["counts"]=={"occurrences":2,"producer_rows":2,"candidate_records":2,
            "distinct_exact_records":2,"duplicate_records":0,"overlap_groups":0,
            "candidate_disagreement_groups":0,"mixed_coordinate_groups":0,"occurrences_without_records":0}
        a,b=linked["occurrences"]
        assert a["source"]==b["source"] and a["occurrence_ordinal"]!=b["occurrence_ordinal"]
        assert {(r["payload"]["source_bit"],r["payload"]["target"]) for r in result["records"]}=={
            (1,TOP+".a"),(0,TOP+".b")}
        # Optional occurrence metadata must not change any legacy payload.
        _,legacy=collect(read_ast(run/"fixture/elaborated_ast.json"),idx)
        for name,rep in reports.items():
            stripped={**rep,"items":[{k:v for k,v in row.items() if k!="occurrence_ordinal"} for row in rep["items"]]}
            assert stripped==legacy[name]
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),
                            ("core",Path(ref["core_reference_report"]).parent/"static")):
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            result,reports,linked=case(name,folder,idx)
            if name=="core":
                check_core(result,reports,linked)
            else:
                assert result["counts"]["producer_rows"]==result["counts"]["candidate_records"]==linked["counts"]["occurrences"]==0
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
