"""Evaluate pinned CV32E40P units independently; retain observed limitations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from rtlprep.annotated_evaluation import evaluate_channel, evaluate_case, load_annotations
from scripts.cv32e40p_pr63 import CASES, COMMIT, REGFILE_WRAPPER, materialize, blob_bytes
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_scalability_pr55 import ALU_FILES
from scripts.rtl_fixtures import load_lock, verify_checkout

ROOT=Path(__file__).resolve().parents[1]

def qualified_labels(case):
    return [{**r,"source":case["owner"]+r["source"],
             "target":case["owner"]+r["target"]} for r in case["labels"]]

def check_structure(case,graph,index):
    top=case["top"]
    assert graph["top"]==index["top"]==top
    instances={i["path"]:i for i in index["instances"]}
    assert len(instances)==len(index["instances"])
    expected={top,top+".rf"} if case["owner"] else {top}
    assert set(instances)==expected,sorted(instances)
    ports={p["name"]:p["direction"] for p in instances[top]["ports"]}
    assert all(ports.get(p)=="In" for p in case["inputs"]),ports
    assert all(ports.get(p)=="Out" for p in case["outputs"]),ports
    nodes=set(graph["nodes"])
    assert len(nodes)==len(graph["nodes"]) and graph["edges"]
    assert all(e["source"] in nodes and e["target"] in nodes for e in graph["edges"])
    if case["owner"]:
        child={p["name"]:p for p in instances[top+".rf"]["ports"]}
        assert child["raddr_a_i"]["type"]=="logic[5:0]",child
        assert child["rdata_a_o"]["type"]=="logic[31:0]",child
        mem=[s for s in index["signals"] if s["instance_path"]==top+".rf" and s["name"]=="mem"]
        assert len(mem)==1 and mem[0]["type"]=="logic[31:0][31:0]",mem

def score_unit(case,graph):
    return evaluate_channel(qualified_labels(case),graph["edges"],"signal",
                            case["top"],set(graph["nodes"]))

def summarize_case(name,graph,index,elapsed,sources,signal,bit=None):
    limits=graph["analysis_limits"]
    return {"name":name,"top":graph["top"],"status":"evaluated",
            "elapsed_seconds":round(elapsed,3),"source_fingerprint":graph["source_fingerprint"],
            "sources":sources,"index_counts":index["counts"],"graph_counts":graph["counts"],
            "analysis_limits":limits,"signal_evaluation":signal,"bit_evaluation":bit,
            "bit_evaluation_status":"labelled_candidates_only" if bit is not None else "not_performed",
            "design_coverage":"not_measured","functional_influence":"not_proven"}

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
    path=run/"multi_unit.result.json"
    report={"status":"incomplete","commit":COMMIT,
            "slang":subprocess.check_output(["slang","--version"],text=True).strip(),
            "cases":[],"design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed","simulation":"not_performed",
            "annotation_scope":"selected_direct_syntactic_candidates_not_representative"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        snapshot=run/"official_sources"
        pins=materialize(upstream,snapshot,entry)
        report["source_blobs"]=pins
        wrapper=run/"regfile_pr63.sv"
        wrapper.write_text(REGFILE_WRAPPER,encoding="utf-8")
        report["wrapper_sha256"]=hashlib.sha256(wrapper.read_bytes()).hexdigest()
        annotation_path=ROOT/"benchmarks/annotations/pr56.json"
        report["frozen_pr56_sha256"]=hashlib.sha256(annotation_path.read_bytes()).hexdigest()
        annotations=load_annotations(annotation_path)
        alu_case=next(c for c in annotations["cases"] if c["name"]=="cv32e40p_alu")
        start=time.monotonic()
        graph,index=extract(run/"alu","cv32e40p_alu",[snapshot/p for p in ALU_FILES],[snapshot/"rtl/include"])
        assert graph["bit_dependency_graph"]["counts"]=={
            "assignments":479,"supported":254,"partial":225,"edges":477,"truncated":False}
        assert index["counts"]["instances"]==4
        score=evaluate_case(alu_case,graph)
        for channel,tp in (("signal",10),("bit",65)):
            assert (score[channel]["tp"],score[channel]["fp"],score[channel]["fn"])==(tp,0,0),score[channel]
        report["cases"].append(summarize_case("alu",graph,index,time.monotonic()-start,
            list(ALU_FILES),score["signal"],score["bit"]))
        save()
        for name,case in CASES.items():
            # Validate provenance lines independently of graph predictions.
            lines=(snapshot/case["file"]).read_text(encoding="utf-8").splitlines()
            assert all(1<=r["line"]<=len(lines) for r in case["labels"]),name
            sources=[snapshot/p for p in case["sources"]]
            if case["owner"]:
                sources.append(wrapper)
            start=time.monotonic()
            graph,index=extract(run/name,case["top"],sources,[snapshot/"rtl/include"])
            check_structure(case,graph,index)
            score=score_unit(case,graph)
            report["cases"].append(summarize_case(name,graph,index,time.monotonic()-start,
                case["sources"]+(["generated:regfile_pr63.sv"] if case["owner"] else []),score))
            save()
        for relative,sha in pins.items():
            assert blob_bytes((snapshot/relative).read_bytes())==sha,relative
        verify_checkout(upstream,entry)
        assert len(report["cases"])==6
        report["status"]="passed"
        report["cases_evaluated"]=6
        report["labelled_signal_totals"]={k:sum(c["signal_evaluation"][k] for c in report["cases"])
                                         for k in ("tp","fp","fn","tn","unknown_labels","unlabelled_predictions")}
        report["interpretation"]="Passed means all six analyses and structural checks ran; labelled misses are reported, not hidden."
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
        save()
        raise
    save()
    for case in report["cases"]:
        score=case["signal_evaluation"]
        print(json.dumps({"name":case["name"],"graph_counts":case["graph_counts"],
                         "signal":{k:score[k] for k in ("tp","fp","fn","tn","precision","recall")},
                         "assessment":case["analysis_limits"]["assessment"],
                         "truncated_analyzers":case["analysis_limits"]["truncated_analyzers"]}))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
