"""Regenerate pinned ALU and whole-core baselines; publish actionable inventory."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.annotated_evaluation import evaluate_case, load_annotations
from scripts.cv32e40p_pr63 import COMMIT, blob_bytes
from scripts.cv32e40p_pr67 import diagnose, UNKNOWN
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_scalability_pr55 import ALU_FILES
from scripts.run_cv32e40p_core_pr65 import execute as run_core
from scripts.rtl_fixtures import load_lock, verify_checkout

ROOT=Path(__file__).resolve().parents[1]

def read_case(directory):
    graph=json.loads((directory/"rtl_dependencies.json").read_text(encoding="utf-8"))
    index=json.loads((directory/"rtl_index.json").read_text(encoding="utf-8"))
    ast=read_ast(directory/"elaborated_ast.json")
    return graph,index,ast

def compact(case):
    return {"top":case["top"],"instances":len(case["instances"]),
            "graph_counts":case["graph_counts"],
            "bit_counts":case["bit_inventory"]["counts"],
            "partial_reasons":case["bit_inventory"]["partial_reasons"],
            "assignment_ast_occurrences":case["syntax_census"]["assignment_count"],
            "truncated_analyzers":case["analysis_limits"]["truncated_analyzers"],
            "truncation_events":{k:v["truncation_events"] for k,v in case["analyzers"].items()
                                 if v["truncation_events"] is not None},
            "warning_reasons":case["warning_reasons"]}

def markdown(cases):
    lines=["# Observed partial-assignment inventory","",
           "Counts are per captured analyzer scope, not design coverage.",""]
    for case in cases:
        lines.extend(["## "+case["top"],"",
            "| Instance | Module | AST assignments | Bit assignments | Supported | Partial | Bit edges |",
            "|---|---|---:|---:|---:|---:|---:|"])
        for path,module in [*case["instances"].items(),(UNKNOWN,"unknown")]:
            c=case["bit_inventory"]["by_instance"][path]
            a=case["syntax_census"]["by_instance"][path]
            lines.append(f"| {path} | {module} | {a.get('assignment_ast',0)} | {c.get('assignments',0)} | {c.get('supported',0)} | {c.get('partial',0)} | {c.get('edges',0)} |")
        lines.extend(["","### Bit partial reasons","","| Reason | Count |","|---|---:|"])
        lines.extend(f"| {r.replace('|',' / ')} | {n} |" for r,n in sorted(case["bit_inventory"]["partial_reasons"].items(),key=lambda x:(-x[1],x[0])))
        lines.extend(["","### Analyzer summary","","| Analyzer | Captured | Partial | Unknown | Global truncated | Nested truncated rows |",
                      "|---|---:|---:|---:|---|---:|"])
        for name,a in case["analyzers"].items():
            d=a["limits"]
            lines.append(f"| {name} | {d['captured']} | {d['status_counts'].get('partial',0)} | {d['status_counts'].get('unknown',0)} | {d['truncated']} | {d['rows_with_nested_truncation']} |")
        lines.append("")
    return "\n".join(lines)+"\n"

def execute(out):
    out=out.resolve()
    entries=load_lock()
    for e in entries:
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    entry=next(e for e in entries if e["repository"]=="openhwfoundation/cv32e40p")
    upstream=ROOT/entry["destination"]
    verify_checkout(upstream,entry)
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"diagnostics.result.json"
    report={"status":"incomplete","commit":COMMIT,"cases":[],"design_coverage":"not_measured",
            "formal_proof":"not_performed","simulation":"not_performed",
            "scope":"observed_analyzer_rows_and_independent_active_syntax_census"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        core_path=run_core(run/"core")
        core_report=json.loads(core_path.read_text())
        core_dir=core_path.parent
        snapshot=core_dir/"official_sources"
        sources=[snapshot/p for p in ALU_FILES]
        alu_dir=run/"alu"
        extract(alu_dir,"cv32e40p_alu",sources,[snapshot/"rtl/include"])
        cases=[]
        for directory in (alu_dir,core_dir/"static"):
            graph,index,ast=read_case(directory)
            case=diagnose(graph,index,ast)
            if directory==alu_dir:
                annotations=load_annotations(ROOT/"benchmarks/annotations/pr56.json")
                frozen=next(c for c in annotations["cases"] if c["name"]=="cv32e40p_alu")
                score=evaluate_case(frozen,graph)
                for channel,tp in (("signal",10),("bit",65)):
                    assert (score[channel]["tp"],score[channel]["fp"],score[channel]["fn"])==(tp,0,0)
                # Historical minimum; the current engine may resolve additional
                # assignments. PR69 compares the exact legacy mode separately.
                bit=case["bit_inventory"]["counts"]
                assert bit["assignments"]==479 and bit["supported"]>=254 and bit["partial"]<=225
                assert bit["edges"]>=477 and not bit["truncated"]
                case["frozen_evaluation"]=score
            else:
                score=core_report["signal_evaluation"]
                assert (score["tp"],score["tn"],score["fp"],score["fn"])==(39,8,0,0)
                assert core_report["path_status_counts"]["observed"]==7
                case["core_signal_evaluation"]=score
                case["core_path_status_counts"]=core_report["path_status_counts"]
            for name in ("expressions","complex_constructs"):
                a=case["analyzers"][name]
                events=a["truncation_events"]
                assert isinstance(events,dict),name
                triggered=events["row_cap_hits"]>0 if name=="expressions" else bool(events["hits"])
                assert triggered==a["counts"]["truncated"],name
            cases.append(case)
            report["cases"].append(case)
            save()
        for relative,sha in core_report["source_blobs"].items():
            assert blob_bytes((snapshot/relative).read_bytes())==sha
        verify_checkout(upstream,entry)
        report["status"]="passed"
        report["core_reference_report"]=str(core_path)
        (run/"diagnostics.summary.md").write_text(markdown(cases),encoding="utf-8")
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save()
        print(f"Report: {path}",flush=True)
    for case in report["cases"]:
        print(json.dumps(compact(case),indent=2))
    print(f"Summary: {run/'diagnostics.summary.md'}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
