"""PR91: reconcile evidence and benchmark fresh-process graph builds.

Linux worker RSS includes AST/index load and graph build; it is not a
phase-specific allocation counter. No performance threshold or coverage claim.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import resource
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter, process_time

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from rtlprep.member_occurrences import collect_linked
from rtlprep.member_evidence import CATEGORIES, natural
from scripts.cv32e40p_pr67 import ast_inventory
from scripts.run_member_sequential_pr90 import check_channel as check_pr90
from scripts.run_member_occurrences_pr87 import check_core as check_pr87
from scripts.run_member_evidence_pr86 import check_lossless
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
OPTIONS={"enable_member_positions":True,"enable_member_combinational":True,"enable_member_sequential":True}
CHANNELS=("member_position_candidates","member_combinational_candidates","member_sequential_candidates")
LINKED_CHANNELS=("array_dependencies","bitwise_dependencies","mux_dependencies",
                 "dynamic_dependencies","selector_recovery","typed_layout")
EXCLUDED={"analysis_limits","source_fingerprint",*CHANNELS}
METRICS=("build_wall_seconds","build_cpu_seconds","peak_rss_after_build_kib",
         "compact_json_bytes","serialization_wall_seconds","peak_rss_after_serialization_kib")


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def historical_digest(graph):
    return digest({k:v for k,v in graph.items() if k not in EXCLUDED})


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def reconcile_flat(graph):
    flat=graph["bit_dependency_graph"]
    items=flat["items"]
    counts=flat["counts"]
    if counts["truncated"] or counts["assignments"]!=len(items):
        raise ValueError("invalid_flat_inventory")
    supported=set()
    for i,row in enumerate(items):
        if row["assignment_id"]!=i:
            raise ValueError("invalid_flat_assignment_id")
        if row["coverage"]!="partial":
            supported.add(i)
    if len(supported)!=counts["supported"] or len(items)-len(supported)!=counts["partial"]:
        raise ValueError("flat_count_disagreement")
    recovered=set()
    per_channel={}
    for name in LINKED_CHANNELS:
        channel=graph[name]
        if channel["counts"].get("truncated"):
            raise ValueError("truncated_linked_channel")
        linked=set()
        for row in channel["items"]:
            if row["coverage"]=="partial" or "flat_assignment_id" not in row:
                continue
            i=row["flat_assignment_id"]
            if not natural(i) or i>=len(items):
                raise ValueError("invalid_linked_flat_id")
            f=items[i]
            if row["target"]!=f["target"] or row.get("source_location")!=f.get("source_location"):
                raise ValueError("linked_flat_metadata_disagreement")
            if i not in supported:
                linked.add(i)
        per_channel[name]={"unique_partial_flat_ids":len(linked),
                           "new_ids_in_channel_order":len(linked-recovered)}
        recovered.update(linked)
    remaining=set(range(len(items)))-supported-recovered
    reasons=Counter(items[i].get("reason","unknown") for i in remaining)
    return {"scope":"historical_flat_assignment_ids_only","flat_assignments":len(items),
            "flat_supported":len(supported),"flat_partial":counts["partial"],
            "linked_partial_ids":len(recovered),"minimum_combined_supported":len(supported|recovered),
            "remaining_without_linked_support":len(remaining),
            "remaining_reasons":dict(reasons),"channels":per_channel,
            "member_occurrences_added":False}


def reconcile_members(graph,envelope,linked):
    expected={r["record_id"]:r for r in envelope["records"]}
    if len(expected)!=len(envelope["records"]):
        raise ValueError("duplicate_inventory_id")
    occurrence={rid:g for g in linked["occurrences"] for rid in g["row_ids"]}
    categories={"position":graph[CHANNELS[0]]["items"],
                **graph[CHANNELS[1]]["collections"],**graph[CHANNELS[2]]["collections"]}
    if set(categories)!=set(CATEGORIES):
        raise ValueError("unexpected_channel_category")
    seen=set()
    site_categories={}
    for category,records in categories.items():
        for r in records:
            rid=r["record_id"]
            if rid in seen or rid not in expected:
                raise ValueError("duplicate_or_unknown_channel_record")
            e=expected[rid]
            if e["category"]!=category or any(r[k]!=e[k] for k in ("producer","row_id","payload")):
                raise ValueError("channel_payload_or_category_disagreement")
            g=occurrence[e["row_id"]]
            if (r["occurrence_ordinal"]!=g["occurrence_ordinal"] or r["instance"]!=g["instance"]
                    or r["context"]!=g["context"] or r["source_location"]!=g["source"]):
                raise ValueError("channel_occurrence_disagreement")
            site_categories.setdefault(g["occurrence_ordinal"],set()).add(category)
            seen.add(rid)
    if seen!=set(expected):
        raise ValueError("missing_channel_record")
    counts={k:len(v) for k,v in categories.items()}
    if any(counts[k]!=envelope["counts"][k] for k in counts):
        raise ValueError("category_count_disagreement")
    return {"scope":"member_inventory_same_ast_only","producer_rows":len(envelope["rows"]),
            "member_occurrences":len(linked["occurrences"]),"occurrences_with_records":len(site_categories),
            "candidate_records":len(expected),"published_records":len(seen),"categories":counts,
            "occurrence_category_sets":dict(Counter("+".join(sorted(v)) for v in site_categories.values())),
            "occurrences_without_records":len(linked["occurrences"])-len(site_categories),
            "exact_payload_and_provenance_match":True,
            "historical_flat_id_mapping":"not_established","design_coverage":"not_measured"}


def paired_summary(samples):
    if not samples:
        raise ValueError("empty_benchmark")
    result={}
    for k in METRICS:
        base=[s["baseline"][k] for s in samples]
        full=[s["all_channels"][k] for s in samples]
        delta=[b-a for a,b in zip(base,full)]
        def stats(xs):
            return {"min":min(xs),"median":median(xs),"max":max(xs)}
        result[k]={"baseline":stats(base),"all_channels":stats(full),"paired_delta":stats(delta)}
    return result


def worker(folder,mode,verify):
    if sys.platform!="linux":
        raise ValueError("RSS benchmark requires Linux ru_maxrss in KiB")
    ast=read_ast(folder/"elaborated_ast.json")
    index=json.loads((folder/"rtl_index.json").read_text())
    start,cpu=perf_counter(),process_time()
    graph=build_dependency_graph(ast,expected_top=index["top"],index=index,
                                 **(OPTIONS if mode=="all_channels" else {}))
    wall,cpu=perf_counter()-start,process_time()-cpu
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start=perf_counter()
    data=encoded(graph)
    serial=perf_counter()-start
    serialized_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={"build_wall_seconds":wall,"build_cpu_seconds":cpu,"peak_rss_after_build_kib":rss,
            "compact_json_bytes":len(data),"serialization_wall_seconds":serial,
            "peak_rss_after_serialization_kib":serialized_rss,
            "full_graph_sha256":hashlib.sha256(data).hexdigest(),
            "historical_graph_sha256":historical_digest(graph),
            "publication_metrics":graph["analysis_limits"]["graph_metrics_excluding_this_report"]}
    del data
    if graph["analysis_limits"]["truncated_analyzers"]:
        raise ValueError("historical_analyzer_truncated")
    if mode=="baseline":
        if any(k in graph for k in CHANNELS):
            raise ValueError("default_channel_regression")
    else:
        if any(graph[k]["truncated"] for k in CHANNELS):
            raise ValueError("member_channel_truncated")
        if verify:
            name="core" if index["top"]=="cv32e40p_core" else "alu"
            envelope,reports,linked=collect_linked(ast,index)
            check_lossless(envelope,reports)
            if name=="core":
                check_pr87(envelope,reports,linked)
            check_pr90(graph[CHANNELS[2]],graph[CHANNELS[0]],graph[CHANNELS[1]],name)
            census=ast_inventory(ast,{r["path"]:r["module"] for r in index["instances"]})
            result["reconciliation"]={
                "ast_syntax_occurrences":census["assignment_count"],
                "historical":reconcile_flat(graph),
                "members":reconcile_members(graph,envelope,linked),
                "historical_warnings":graph["warnings"],
                "limitations":{"functional_influence":"not_proven","formal_proof":"not_performed",
                               "design_coverage":"not_measured"}}
    return result


def execute(out,reference=None,repeats=3):
    if type(repeats) is not int or not 2<=repeats<=10:
        raise ValueError("repeats must be 2..10")
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","repeats":repeats,"cases":[],
            "protocol":"fresh Linux processes, same AST/index files, alternating order; first all-channel worker verifies after timing",
            "rss_scope":"process high-water RSS including load; not isolated graph allocation",
            "size_scope":"compact sorted ASCII JSON, includes analysis_limits, excludes pipeline-added fingerprint",
            "environment":{"python":sys.version,"platform":platform.platform(),"machine":platform.machine()},
            "design_coverage":"not_measured","functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),("core",Path(ref["core_reference_report"]).parent/"static")):
            hashes={f:file_hash(folder/f) for f in ("elaborated_ast.json","rtl_index.json")}
            legacy=json.loads((folder/"rtl_dependencies.json").read_text())
            hist=historical_digest(legacy)
            del legacy
            case={"name":name,"input_sha256":hashes,"samples":[]}
            report["cases"].append(case)
            full_hashes=set()
            base_hashes=set()
            for i in range(repeats):
                order=("baseline","all_channels") if i%2==0 else ("all_channels","baseline")
                pair={"order":list(order)}
                case["samples"].append(pair)
                for mode in order:
                    cmd=[sys.executable,"-m","scripts.run_member_benchmark_pr91",
                         "--worker",str(folder),"--mode",mode]
                    if mode=="all_channels" and i==0:
                        cmd.append("--verify")
                    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=180)
                    if proc.returncode:
                        raise RuntimeError("worker failed: "+proc.stderr[-4000:])
                    sample=json.loads(proc.stdout)
                    assert sample["historical_graph_sha256"]==hist
                    if mode=="all_channels":
                        full_hashes.add(sample["full_graph_sha256"])
                    else:
                        base_hashes.add(sample["full_graph_sha256"])
                    if "reconciliation" in sample:
                        case["reconciliation"]=sample.pop("reconciliation")
                    pair[mode]=sample
                    save()
            assert len(full_hashes)==len(base_hashes)==1
            assert hashes=={f:file_hash(folder/f) for f in hashes}
            recon=case["reconciliation"]
            old=recon["historical"]
            members=recon["members"]
            expected=(3811,1199,815,384,30,1481) if name=="core" else (612,479,381,98,0,0)
            actual=(recon["ast_syntax_occurrences"],old["flat_assignments"],old["minimum_combined_supported"],
                    old["remaining_without_linked_support"],members["member_occurrences"],members["published_records"])
            assert actual==expected,actual
            case["summary"]=paired_summary(case["samples"])
            case["historical_graph_unchanged"]=True
            case["same_input_determinism"]=True
            save()
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:4500])
        raise
    finally:
        save()
        print(f"Summary: {path}",flush=True)
        print(path.read_text(),flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--worker",type=Path)
    p.add_argument("--mode",choices=("baseline","all_channels"))
    p.add_argument("--verify",action="store_true")
    args=p.parse_args()
    if args.worker is not None:
        if args.mode is None:
            p.error("--mode required with --worker")
        print(json.dumps(worker(args.worker,args.mode,args.verify)))
    else:
        if args.out is None:
            p.error("--out required")
        execute(args.out,args.reference,args.repeats)
