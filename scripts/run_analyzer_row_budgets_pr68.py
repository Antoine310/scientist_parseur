"""Compare legacy and expanded row policies on identical elaborated ASTs."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

from rtlprep.analysis_budgets import AnalysisBudget, read_ast
from rtlprep.dependencies import build_dependency_graph
from rtlprep.index import build_index
from scripts.run_cv32e40p_diagnostics_pr67 import execute as run_diagnostics
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
LEGACY=2000
EXPANDED=4096
TARGETS=("expressions","complex_constructs")
DERIVED={"expressions","complex_constructs","coverage","analysis_limits"}

def canonical(row):
    return json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))

def compare_graphs(before,after):
    """Only the two inventories and their derived diagnostics may change."""
    b={k:v for k,v in before.items() if k not in DERIVED}
    a={k:v for k,v in after.items() if k not in DERIVED}
    if b!=a:
        changed=sorted(k for k in set(b)|set(a) if b.get(k)!=a.get(k))
        raise ValueError("non-target graph changed: "+", ".join(changed))
    result={}
    for name in TARGETS:
        old,new=before[name],after[name]
        old_rows=Counter(canonical(r) for r in old["items"])
        new_rows=Counter(canonical(r) for r in new["items"])
        if old_rows-new_rows:
            raise ValueError("previous rows lost or modified: "+name)
        if name=="complex_constructs" and new["items"][:len(old["items"])]!=old["items"]:
            raise ValueError("complex construct traversal order changed")
        old_limit=before["analysis_limits"]["analyzers"][name]
        new_limit=after["analysis_limits"]["analyzers"][name]
        if old_limit["captured"]!=len(old["items"]) or new_limit["captured"]!=len(new["items"]):
            raise ValueError("inventory mismatch: "+name)
        result[name]={"before":old_limit,"after":new_limit,
                      "added_rows":len(new["items"])-len(old["items"]),
                      "before_events":old["truncation_events"],"after_events":new["truncation_events"]}
    return result

def worker(ast_path,top,out,rows):
    if sys.platform!="linux":
        raise RuntimeError("Linux required for KiB RSS")
    budget=AnalysisBudget(expression_rows=rows,complex_rows=rows)
    out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    ast=read_ast(ast_path,budget)
    after_read=time.perf_counter()
    idx=build_index(ast,expected_top=top)
    after_index=time.perf_counter()
    graph=build_dependency_graph(ast,expected_top=top,index=idx,budget=budget)
    after_graph=time.perf_counter()
    path=out/"rtl_dependencies.json"
    path.write_text(json.dumps(graph,indent=2,ensure_ascii=False),encoding="utf-8")
    end=time.perf_counter()
    report={"status":"passed","row_limit":rows,
            "ast_sha256":hashlib.sha256(ast_path.read_bytes()).hexdigest(),
            "seconds":{"ast_read":after_read-start,"index":after_index-after_read,
                       "graph":after_graph-after_index,"serialization":end-after_graph,
                       "total_without_slang":end-start},
            "peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "graph_bytes":path.stat().st_size}
    (out/"measurement.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

def run_policy(ast,top,directory,rows):
    subprocess.run([sys.executable,"-m","scripts.run_analyzer_row_budgets_pr68",
                    "--worker-ast",str(ast),"--top",top,"--out",str(directory),
                    "--rows",str(rows)],cwd=ROOT,check=True,timeout=300)
    graph=json.loads((directory/"rtl_dependencies.json").read_text(encoding="utf-8"))
    measurement=json.loads((directory/"measurement.json").read_text(encoding="utf-8"))
    return graph,measurement

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"row_budgets.result.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed",
            "scope":"same_ast_legacy_vs_expanded_row_policy",
            "settings":{"legacy_rows":LEGACY,"expanded_rows":EXPANDED,
                        "measurements":"one fresh Linux process per design/policy, excluding slang"}}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        diag_path=run_diagnostics(run/"reference")
        diag=json.loads(diag_path.read_text(encoding="utf-8"))
        core_dir=Path(diag["core_reference_report"]).parent/"static"
        report["reference_diagnostics"]=str(diag_path)
        for name,top,directory,expected in [
            ("alu","cv32e40p_alu",diag_path.parent/"alu",(479,254,225,477)),
            ("core","cv32e40p_core",core_dir,(1199,467,732,2842))]:
            ast=directory/"elaborated_ast.json"
            old,old_m=run_policy(ast,top,run/name/"legacy",LEGACY)
            new,new_m=run_policy(ast,top,run/name/"expanded",EXPANDED)
            if old_m["ast_sha256"]!=new_m["ast_sha256"]:
                raise ValueError("different AST bytes")
            delta=compare_graphs(old,new)
            if (old["bit_dependency_graph"]["counts"]["assignments"],
                old["bit_dependency_graph"]["counts"]["supported"],
                old["bit_dependency_graph"]["counts"]["partial"],
                old["bit_dependency_graph"]["counts"]["edges"])!=expected:
                raise ValueError("PR67 bit baseline mismatch: "+name)
            if new["expressions"]["truncation_events"]["row_cap_hits"] or new["complex_constructs"]["truncation_events"]["hits"].get("row_cap"):
                raise ValueError("expanded row cap still hit: "+name)
            if name=="core":
                if not old["expressions"]["truncation_events"]["row_cap_hits"] or not old["complex_constructs"]["truncation_events"]["hits"].get("row_cap"):
                    raise ValueError("PR67 row cap baseline not reproduced")
                if any(d["added_rows"]<=0 for d in delta.values()):
                    raise ValueError("no rows recovered")
            elif any(d["added_rows"] for d in delta.values()):
                raise ValueError("unexpected ALU inventory change")
            residual=new["analysis_limits"]["truncated_analyzers"]
            case={"name":name,"top":top,"unchanged_non_target_graph":True,
                  "bit_counts":new["bit_dependency_graph"]["counts"],"graph_counts":new["counts"],
                  "row_comparison":delta,"truncated_before":old["analysis_limits"]["truncated_analyzers"],
                  "truncated_after":residual,
                  "coverage_findings_truncated_after":new["analysis_limits"]["coverage_findings_truncated"],
                  "assessment_after":new["analysis_limits"]["assessment"],
                  "targeted_row_caps_removed":True,
                  "measurement_before":old_m,"measurement_after":new_m}
            report["cases"].append(case)
            save()
            print(json.dumps({"name":name,"rows":{k:{"before":v["before"]["captured"],
                          "after":v["after"]["captured"],"partial_after":v["after"]["status_counts"].get("partial",0),
                          "added":v["added_rows"],"events_after":v["after_events"]} for k,v in delta.items()},
                          "truncated_before":case["truncated_before"],"truncated_after":residual,
                          "bit_counts":case["bit_counts"],"measurement_before":old_m,
                          "measurement_after":new_m},indent=2),flush=True)
        report["status"]="passed"
        report["all_analyzer_truncations_removed"]=not any(c["truncated_after"] for c in report["cases"])
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save()
        print(f"Report: {path}",flush=True)
    return path

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--worker-ast",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--top",help=argparse.SUPPRESS)
    parser.add_argument("--rows",type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker_ast:
        worker(args.worker_ast,args.top,args.out,args.rows)
    else:
        execute(args.out)
