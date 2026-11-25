"""First whole-core analysis on pinned CV32E40P, with fresh-worker measurements."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from rtlprep.annotated_evaluation import evaluate_channel
from rtlprep.analysis_budgets import read_ast
from rtlprep.constant_indices import integer_value
from scripts.cv32e40p_pr63 import COMMIT, materialize, blob_bytes
from scripts.cv32e40p_pr65 import (
    TOP, CORE_FILE, MANIFEST, CORE_PINS, SOURCES, CONFIG, INSTANCE_MODULES,
    INPUTS, OUTPUTS, LABELS, PATHS, check_manifest, find_path,
)
from scripts.rtl_fixtures import load_lock, verify_checkout, git
from scripts.run_scalability_pr55 import write_manifest

ROOT=Path(__file__).resolve().parents[1]

def expected_instances():
    return {TOP+("."+p if p else ""):module for p,module in INSTANCE_MODULES.items()}

def check_structure(graph,index):
    if graph["top"]!=TOP or index["top"]!=TOP:
        raise ValueError("wrong elaborated top")
    actual={i["path"]:i["module"] for i in index["instances"]}
    expected=expected_instances()
    if actual!=expected or len(actual)!=len(index["instances"]):
        raise ValueError(f"active hierarchy mismatch: missing={sorted(set(expected.items())-set(actual.items()))}, unexpected={sorted(set(actual.items())-set(expected.items()))}")
    top=next(i for i in index["instances"] if i["path"]==TOP)
    ports={p["name"]:p["direction"] for p in top["ports"]}
    if not all(ports.get(p)=="In" for p in INPUTS) or not all(ports.get(p)=="Out" for p in OUTPUTS):
        raise ValueError("missing or wrongly directed core interface")
    nodes=set(graph["nodes"])
    if len(nodes)!=len(graph["nodes"]) or not graph["edges"]:
        raise ValueError("empty or duplicate graph nodes")
    if not all(e["source"] in nodes and e["target"] in nodes for e in graph["edges"]):
        raise ValueError("dangling graph endpoint")
    return actual

def check_config(ast):
    roots=[n for n in ast["design"]["members"] if n.get("kind")=="Instance" and n.get("name")==TOP]
    if len(roots)!=1:
        raise ValueError("missing unique core instance")
    params={n["name"]:integer_value(n.get("value")) for n in roots[0]["body"]["members"]
            if n.get("kind")=="Parameter" and n.get("isPort") is True}
    actual={k:params.get(k) for k in CONFIG}
    if actual!=CONFIG:
        raise ValueError(f"unexpected elaborated configuration: {actual}")
    return actual

def score_core(graph):
    return evaluate_channel(LABELS,graph["edges"],"signal",TOP,set(graph["nodes"]))

def run_worker(manifest,directory,timeout):
    # Fresh process, same measurement protocol as PR55; slang timeout
    # and outer Python pipeline timeout are separate, not CPU/RSS quotas.
    command=[sys.executable,"-m","scripts.run_scalability_pr55","--worker",
             "--manifest",str(manifest),"--out",str(directory),"--timeout",str(timeout)]
    subprocess.run(command,check=True,timeout=timeout+120,cwd=ROOT)
    return json.loads((directory/"sample.json").read_text(encoding="utf-8"))

def execute(out,timeout=180):
    if type(timeout) is not int or not 10<=timeout<=600:
        raise ValueError("timeout must be 10..600 seconds")
    if sys.platform!="linux":
        raise RuntimeError("Linux required for peak RSS in KiB")
    out=out.resolve()
    entries=load_lock()
    for entry in entries:
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    entry=next(e for e in entries if e["repository"]=="openhwfoundation/cv32e40p")
    upstream=ROOT/entry["destination"]
    verify_checkout(upstream,entry)
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"core.result.json"
    report={"schema_version":1,"status":"incomplete","phase":"source_snapshot",
            "top":TOP,"commit":COMMIT,"configuration_requested":CONFIG,
            "clock_gate":"official_simulation_model_not_for_synthesis",
            "environment":{"python":sys.version.split()[0],"platform":platform.platform(),
                "logical_cpu_count":os.cpu_count(),"rtlprep_revision":git(ROOT,"rev-parse","HEAD"),
                "tracked_worktree_dirty":bool(git(ROOT,"status","--porcelain","--untracked-files=no")),
                "slang":subprocess.check_output(["slang","--version"],text=True,timeout=10).strip()},
            "settings":{"timeout_seconds":timeout,"samples":1,"defines":[]},
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed","simulation":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        snapshot=run/"official_sources"
        pins=materialize(upstream,snapshot,entry,additional_pins=CORE_PINS)
        files=check_manifest((snapshot/MANIFEST).read_text(encoding="utf-8"))
        if set(files)|{MANIFEST}!=set(pins):
            raise ValueError("compiled source inventory and pins disagree")
        report.update(source_blobs=pins,compiled_sources=files,phase="analysis")
        save()
        manifest=run/"design.json"
        write_manifest(manifest,TOP,[snapshot/p for p in files],[snapshot/"rtl/include"])
        directory=run/"static"
        sample=run_worker(manifest,directory,timeout)
        report["measurement"]=sample
        graph=json.loads((directory/"rtl_dependencies.json").read_text())
        index=json.loads((directory/"rtl_index.json").read_text())
        report.update(phase="structural_validation",source_fingerprint=graph["source_fingerprint"],
                      index_counts=index["counts"],graph_counts=graph["counts"],
                      analysis_limits=graph["analysis_limits"])
        save()
        config=check_config(read_ast(directory/"elaborated_ast.json"))
        instances=check_structure(graph,index)
        report.update(configuration_elaborated=config,instances=instances,phase="annotation_evaluation")
        save()
        lines=(snapshot/CORE_FILE).read_text().splitlines()
        if len(LABELS)!=47 or not all(1<=r["line"]<=len(lines) for r in LABELS):
            raise ValueError("invalid label provenance")
        score=score_core(graph)
        report["signal_evaluation"]=score
        report["cross_instance_paths"]=[
            {"source":s,"target":t,**find_path(graph,TOP+"."+s,TOP+"."+t)}
            for s,t in PATHS]
        report["path_status_counts"]={status:sum(p["status"]==status for p in report["cross_instance_paths"])
                                      for status in ("observed","not_observed","budget_exhausted")}
        report["phase"]="source_reverification"
        save()
        for relative,sha in pins.items():
            if blob_bytes((snapshot/relative).read_bytes())!=sha:
                raise ValueError("source snapshot changed: "+relative)
        verify_checkout(upstream,entry)
        report.update(status="passed",phase="complete",
                      interpretation="Successful elaboration and structural evaluation, not complete or functionally proven analysis. Annotation misses and path limitations are measured, not suppressed.")
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save()
        print(f"Report: {path}",flush=True)
    print(json.dumps({"status":report["status"],"instances":len(instances),
        "index_counts":index["counts"],"graph_counts":graph["counts"],
        "signal":{k:score[k] for k in ("tp","tn","fp","fn","precision","recall","f1")},
        "path_status_counts":report["path_status_counts"],
        "assessment":report["analysis_limits"]["assessment"],
        "truncated_analyzers":report["analysis_limits"]["truncated_analyzers"],
        "seconds":sample["seconds"],"peak_rss_kib":sample["peak_rss_kib"],
        "bytes":sample["bytes"]},indent=2))
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=180)
    args=p.parse_args()
    execute(args.out,args.timeout)
