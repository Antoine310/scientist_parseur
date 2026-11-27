"""Reconcile residuals against pinned fresh ALU/core diagnostics."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter

from rtlprep.analysis_budgets import read_ast
from rtlprep.residual_audit import audit_residuals
from scripts.run_member_benchmark_pr91 import reconcile_flat, file_hash, digest
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={"alu":(479,254,127,98,{"partial_bit_access":96,"unproven_packed_layout":1,"target_rhs_width_mismatch":1}),
          "core":(1199,531,284,384,{"partial_bit_access":371,"unvalidated_ast_positions":10,
                                   "unproven_packed_layout":2,"target_rhs_width_mismatch":1})}


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
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        for name,folder in (("alu",ref.parent/"alu"),("core",Path(d["core_reference_report"]).parent/"static")):
            files=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
            hashes={f:file_hash(folder/f) for f in files}
            ast=read_ast(folder/files[0])
            idx=json.loads((folder/files[1]).read_text())
            graph=json.loads((folder/files[2]).read_text())
            before=digest(graph)
            start=perf_counter()
            result=audit_residuals(ast,idx,graph)
            elapsed=perf_counter()-start
            old=reconcile_flat(graph)
            n,base,recovered,left,coarse=EXPECTED[name]
            assert (result["flat_assignments"],result["flat_supported"],result["recovered_unique_ids"],
                    result["residual_count"],result["coarse_reasons"])==(n,base,recovered,left,coarse)
            assert old["minimum_combined_supported"]==result["minimum_combined_supported"]
            assert old["remaining_reasons"]==result["coarse_reasons"]
            assert sum(result["detailed_reasons"].values())==left
            assert sum(result["rhs_root_groups"].values())==left
            assert sum(result["by_instance"].values())==left
            assert result["syntax_scan_limited_rows"]==0
            assert digest(graph)==before and hashes=={f:file_hash(folder/f) for f in files}
            detail=run/(name+".residuals.json")
            detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
            report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
                                    "detail_file":detail.name,"historical_unchanged":True,
                                    **{k:v for k,v in result.items() if k not in ("rows","recovered_ids","residual_ids")}})
            save()
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:4000])
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
