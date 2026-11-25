"""Pinned official EX-stage analysis and selected behavioral validation."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time

from rtlprep.annotated_evaluation import evaluate_channel
from scripts.cv32e40p_pr63 import COMMIT, materialize, blob_bytes
from scripts.cv32e40p_pr64 import TOP, EX_FILE, EX_PINS, SOURCES, INSTANCES, INPUTS, OUTPUTS, LABELS, PATHS, find_path
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock, verify_checkout

ROOT=Path(__file__).resolve().parents[1]

def check_structure(graph,index):
    assert graph["top"]==index["top"]==TOP
    instances={i["path"]:i for i in index["instances"]}
    assert set(instances)==INSTANCES and len(instances)==len(index["instances"]),sorted(instances)
    ports={p["name"]:p["direction"] for p in instances[TOP]["ports"]}
    assert all(ports.get(p)=="In" for p in INPUTS),ports
    assert all(ports.get(p)=="Out" for p in OUTPUTS),ports
    nodes=set(graph["nodes"])
    assert len(nodes)==len(graph["nodes"])
    assert graph["edges"] and all(e["source"] in nodes and e["target"] in nodes for e in graph["edges"])
    return sorted(instances)

def execute(out):
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
    path=run/"ex_stage.result.json"
    report={"status":"incomplete","commit":COMMIT,"top":TOP,
            "configuration":{"FPU":0,"COREV_PULP":0},
            "slang":subprocess.check_output(["slang","--version"],text=True).strip(),
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed","simulation":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        snapshot=run/"official_sources"
        pins=materialize(upstream,snapshot,entry,additional_pins=EX_PINS)
        sources=[snapshot/p for p in SOURCES]
        includes=[snapshot/"rtl/include"]
        report.update(source_blobs=pins,compiled_sources=SOURCES)
        lines=(snapshot/EX_FILE).read_text().splitlines()
        assert len(LABELS)==44 and all(1<=r["line"]<=len(lines) for r in LABELS)
        start=time.monotonic()
        graph,index=extract(run/"static",TOP,sources,includes)
        instance_paths=check_structure(graph,index)
        score=evaluate_channel(LABELS,graph["edges"],"signal",TOP,set(graph["nodes"]))
        paths=[{"source":s,"target":t,**find_path(graph,TOP+"."+s,TOP+"."+t)}
               for s,t in PATHS]
        report.update(source_fingerprint=graph["source_fingerprint"],instance_paths=instance_paths,
                      index_counts=index["counts"],graph_counts=graph["counts"],
                      analysis_limits=graph["analysis_limits"],signal_evaluation=score,
                      cross_instance_paths=paths,static_elapsed_seconds=round(time.monotonic()-start,3))
        save()
        # Only the reviewed direct bindings and local assignments are strict.
        assert (score["tp"],score["fp"],score["fn"],score["tn"])==(36,0,0,8),score
        assert all(p["status"]=="observed" for p in paths),paths
        assert all(any(e["kind"]=="port_input" for e in p["edges"]) and
                   any(e["kind"]=="port_output" for e in p["edges"]) for p in paths),paths
        counts,_=simulate(sources,TOP,"rtlprep.sim_tests.cv32e40p_ex_stage_pr64",run/"simulation",includes)
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0),counts
        report.update(simulation="passed",behavioral_vectors=64,behavioral_scenarios=384,
                      simulation_scope="selected_two_state_combinational_forwarding_and_branch_checks")
        for relative,sha in pins.items():
            assert blob_bytes((snapshot/relative).read_bytes())==sha,relative
        verify_checkout(upstream,entry)
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
        save()
        raise
    save()
    print(json.dumps({"status":report["status"],"instance_paths":report["instance_paths"],
                      "graph_counts":report["graph_counts"],
                      "signal":{k:score[k] for k in ("tp","tn","fp","fn","precision","recall")},
                      "observed_paths":len(paths),"behavioral_scenarios":384,
                      "truncated_analyzers":report["analysis_limits"]["truncated_analyzers"]},indent=2))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
