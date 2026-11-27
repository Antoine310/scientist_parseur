"""Independent reconciliation of active syntax occurrences and historical rows."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.capture_audit import audit_capture
from scripts.cv32e40p_pr67 import ast_inventory
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_benchmark_pr91 import file_hash,digest
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="capture_audit_pr102"
FIXTURE=ROOT/"tests/fixtures/capture_audit_pr102.sv"


def check(result,name):
    c=result["counts"]
    expected={"fixture":(3,1),"alu":(612,479),"core":(3811,1199)}[name]
    assert (c["ast_occurrences"],c["historical_rows"])==expected,c
    assert sum(c["classification"].values())==expected[0]
    assert c["classification"]["captured"]==expected[1]
    assert {r["flat_assignment_id"] for r in result["items"] if r["flat_assignment_id"] is not None}==set(range(expected[1]))
    if name=="fixture":
        assert c["classification"]=={"captured":1,"selection_gate_missed_syntax":1,"no_selection_syntax_in_operands":1}
        assert c["missed_with_call_argument_selection"]==1
        omitted=next(r for r in result["items"] if r["classification"]=="selection_gate_missed_syntax")
        assert omitted["lhs_kind"]=="NamedValue" and omitted["rhs_kind"]=="BinaryOp"
        assert omitted["call_argument_selection"]
    assert result["complete_within_scope"] and result["historical_replay_exact"]


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
            "functional_influence":"not_proven","formal_proof":"not_applicable_to_syntax_census"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder):
        files=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
        hashes={f:file_hash(folder/f) for f in files}
        ast=read_ast(folder/files[0])
        idx=json.loads((folder/files[1]).read_text())
        g=json.loads((folder/files[2]).read_text())
        before=digest(g)
        start=perf_counter()
        result=audit_capture(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".capture-audit.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(result,name)
        prior=ast_inventory(ast,{r["path"]:r["module"] for r in idx["instances"]})
        assert prior["assignment_count"]==result["counts"]["ast_occurrences"]
        for owner,counts in prior["by_instance"].items():
            assert counts.get("assignment_ast",0)==sum(result["by_instance"].get(owner,{}).values())
        assert digest(g)==before and hashes=={f:file_hash(folder/f) for f in files}
        report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
             "historical_unchanged":True,"pr67_census_reconciled":True,"detail_file":detail.name,
             **{k:v for k,v in result.items() if k!="items"}})
        save()
    try:
        extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture")
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
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
