"""Reproducible Linux scaling benchmark for the real slang + RTLPrep pipeline.

Fresh Python process per sample. No timing thresholds other than a timeout;
semantic checks and explicit analyzer limits are independent of performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time

from rtlprep.analysis_budgets import read_ast
from rtlprep.index import build_index
from rtlprep.dependencies import build_dependency_graph
from rtlprep.manifest import load_design
from rtlprep.runner import analyze, fingerprint
from scripts.rtl_fixtures import load_lock, verify_checkout

ROOT=Path(__file__).resolve().parents[1]
TOP="scale_pr55"
DEFAULT_SIZES=(8,64,256,520)
ANALYZERS=("expressions","register_flow","sequential_candidates","intercycle_dependencies",
           "bit_accesses","bit_dependency_graph","complex_constructs")
ALU_FILES=("rtl/include/cv32e40p_pkg.sv","rtl/cv32e40p_popcnt.sv",
           "rtl/cv32e40p_ff_one.sv","rtl/cv32e40p_alu_div.sv","rtl/cv32e40p_alu.sv")


def validate_sizes(sizes):
    if not sizes or len(sizes)>8 or any(type(n) is not int or not 1<=n<=1024 for n in sizes):
        raise ValueError("choose 1-8 stage counts between 1 and 1024")
    if sorted(set(sizes))!=list(sizes):
        raise ValueError("stage counts must be strictly increasing")
    return tuple(sizes)


def generate_pipeline(n):
    validate_sizes([n])
    lines=["module scale_stage55(input logic clk, input logic [7:0] d, output logic [7:0] q);",
           "  logic [7:0] perm;",
           "  assign perm = {d[3:0], d[7:4]};",
           "  always_ff @(posedge clk) q <= perm;",
           "endmodule",
           "module scale_pr55(input logic clk, input logic [7:0] data_i, output logic [7:0] result_o);"]
    for i in range(n-1):
        lines.append(f"  logic [7:0] link_{i};")
    for i in range(n):
        src="data_i" if i==0 else f"link_{i-1}"
        dst="result_o" if i==n-1 else f"link_{i}"
        lines.append(f"  scale_stage55 stage_{i}(.clk(clk), .d({src}), .q({dst}));")
    return "\n".join(lines+["endmodule",""])


def write_manifest(path,top,sources,includes=()):
    path.write_text(json.dumps({"top":top,"sources":[str(p) for p in sources],
        "include_dirs":[str(p) for p in includes],"defines":[]},indent=2),encoding="utf-8")


def oracle(index,graph,n):
    """Exact fixture hierarchy, observed signal links and bit positions."""
    expected_instances={TOP}|{f"{TOP}.stage_{i}" for i in range(n)}
    actual_instances={r["path"] for r in index["instances"]}
    if actual_instances!=expected_instances:
        raise ValueError("fixture instance identity mismatch")
    edges={(e["source"],e["target"],e["kind"],e["sequential"]) for e in graph["edges"]}
    required=set()
    expected_bits=set()
    for i in range(n):
        p=f"{TOP}.stage_{i}"
        src=TOP+(".data_i" if i==0 else f".link_{i-1}")
        dst=TOP+(".result_o" if i==n-1 else f".link_{i}")
        required.update({(TOP+".clk",p+".clk","port_input",False),
                         (src,p+".d","port_input",False),
                         (p+".q",dst,"port_output",False),
                         (p+".d",p+".perm","data",False),
                         (p+".perm",p+".q","data",True)})
        expected_bits.update((p+".d",b,p+".perm",(b+4)%8) for b in range(8))
    if not required<=edges:
        raise ValueError(f"missing required signal links: {len(required-edges)}")
    bits=graph["bit_dependency_graph"]
    actual_bits={(e["source"],e["source_bit"],e["target"],e["target_bit"]) for e in bits["edges"]}
    if not actual_bits<=expected_bits or len(actual_bits)!=len(bits["edges"]):
        raise ValueError("unexpected or duplicate bit candidates")
    if actual_bits!=expected_bits and not bits["counts"]["truncated"]:
        raise ValueError("missing bit candidates without truncation")
    if n>512 and not graph["register_flow"]["counts"]["truncated"]:
        raise ValueError("expected register-flow budget boundary not reported")
    if n<=512 and graph["register_flow"]["counts"]["truncated"]:
        raise ValueError("unexpected register-flow truncation below process budget")
    return {"instances":len(expected_instances),"required_signal_links":len(required),
            "matched_signal_links":len(required&edges),"reviewed_bit_positions":len(expected_bits),
            "matched_bit_positions":len(actual_bits),"register_flow_budget_probe":n>512}


def metrics(index,graph):
    return {"index_counts":index["counts"],"graph_counts":graph["counts"],
            "analyzer_counts":{k:graph[k]["counts"] for k in ANALYZERS},
            "coverage_assessment":graph["coverage"]["assessment"],
            "design_coverage":"not_measured"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(manifest,out,timeout,stages):
    if sys.platform!="linux":
        raise RuntimeError("Linux required for KiB ru_maxrss semantics")
    out.mkdir(parents=True,exist_ok=False)
    design=load_design(manifest)
    start=time.perf_counter()
    result=analyze(design,out,timeout)
    analysis_seconds=time.perf_counter()-start
    if result["status"]!="passed":
        raise RuntimeError(f"slang/analyze failed: {result}")
    # A fresh worker has executed only the slang subprocess at this point.
    slang_peak=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t=time.perf_counter()
    ast=read_ast(out/"elaborated_ast.json")
    load_seconds=time.perf_counter()-t
    t=time.perf_counter()
    idx=build_index(ast,expected_top=design.top)
    index_seconds=time.perf_counter()-t
    t=time.perf_counter()
    graph=build_dependency_graph(ast,expected_top=design.top,index=idx)
    graph_seconds=time.perf_counter()-t
    t=time.perf_counter()
    source_fp=fingerprint(design)
    idx.update(source_fingerprint=source_fp,manifest=str(design.manifest),
               sources=[str(p) for p in design.sources])
    graph["source_fingerprint"]=source_fp
    for name,value in (("rtl_index.json",idx),("rtl_dependencies.json",graph)):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    serialize_seconds=time.perf_counter()-t
    total=time.perf_counter()-start
    python_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    checks=oracle(idx,graph,stages) if stages is not None else None
    if not graph["nodes"] or not graph["edges"]:
        raise ValueError("empty benchmark graph")
    report={"status":"passed","stages":stages,"source_fingerprint":source_fp,
            "source_sha256":[sha256(p) for p in design.sources],
            "seconds":{"slang_reported":result["elapsed_seconds"],"analyze_including_summary":analysis_seconds,
                       "ast_reload":load_seconds,"index_build":index_seconds,"graph_build":graph_seconds,
                       "serialization_and_fingerprint":serialize_seconds,"pipeline_total":total},
            "peak_rss_kib":{"python_worker":python_peak,"slang_child":slang_peak},
            "bytes":{name:(out/name).stat().st_size for name in
                     ("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")},
            "semantic_metrics":metrics(idx,graph),"fixture_oracle":checks}
    (out/"sample.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def summarize(samples):
    if not samples or any(s.get("status")!="passed" for s in samples):
        raise ValueError("all repetitions must succeed")
    first=samples[0]
    for other in samples[1:]:
        for key in ("stages","source_fingerprint","source_sha256","semantic_metrics","fixture_oracle"):
            if other[key]!=first[key]:
                raise ValueError(f"nonreproducible semantic field: {key}")
    def distribution(key):
        return {name:{"min":min(s[key][name] for s in samples),
                      "median":statistics.median(s[key][name] for s in samples),
                      "max":max(s[key][name] for s in samples)} for name in first[key]}
    return {"repetitions":len(samples),"semantic_metrics":first["semantic_metrics"],
            "fixture_oracle":first["fixture_oracle"],"source_sha256":first["source_sha256"],
            "seconds":distribution("seconds"),"peak_rss_kib":distribution("peak_rss_kib"),
            "bytes":distribution("bytes")}


def execute(out,sizes=DEFAULT_SIZES,repetitions=3,timeout=180,include_alu=True):
    sizes=validate_sizes(sizes)
    if type(repetitions) is not int or not 1<=repetitions<=5 or not 10<=timeout<=600:
        raise ValueError("invalid repetition or timeout bound")
    if sys.platform!="linux":
        raise RuntimeError("Linux required")
    out=out.resolve()
    entries=load_lock()
    for fixture in entries:
        upstream_path=(ROOT/fixture["destination"]).resolve()
        if out==upstream_path or out.is_relative_to(upstream_path):
            raise ValueError("output must not be inside official RTL checkout")
    entry=next(e for e in entries if e["repository"]=="openhwfoundation/cv32e40p") if include_alu else None
    if entry:
        upstream=ROOT/entry["destination"]
        verify_checkout(upstream,entry)
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    cpu_model=next((line.split(":",1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name") and ":" in line),None)
    report={"schema_version":1,"status":"incomplete","environment":{
        "platform":platform.platform(),"python":sys.version.split()[0],"cpu_count":os.cpu_count(),
        "cpu_model":cpu_model,"machine":platform.machine(),
        "tracked_worktree_dirty":bool(subprocess.run(["git","-C",str(ROOT),"status","--porcelain","--untracked-files=no"],
            capture_output=True,text=True,check=True,timeout=10).stdout.strip()),
        "slang":subprocess.run(["slang","--version"],capture_output=True,text=True,check=True,timeout=10).stdout.strip(),
        "rtlprep_revision":subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],
            capture_output=True,text=True,check=True,timeout=10).stdout.strip()},
        "settings":{"sizes":list(sizes),"repetitions":repetitions,"timeout_seconds":timeout,
                    "include_pinned_alu":include_alu},
        "cases":[],"design_coverage":"not_measured","formal_proof":"not_performed"}
    report_path=run/"scalability.result.json"
    def save():
        report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    cases=[]
    for n in sizes:
        case=run/f"pipeline_{n}"
        case.mkdir()
        source=case/"pipeline.sv"
        source.write_text(generate_pipeline(n),encoding="utf-8")
        manifest=case/"design.json"
        write_manifest(manifest,TOP,[source])
        cases.append((case,manifest,n))
    if entry:
        case=run/"cv32e40p_alu"
        case.mkdir()
        manifest=case/"design.json"
        write_manifest(manifest,"cv32e40p_alu",[upstream/p for p in ALU_FILES],[upstream/"rtl/include"])
        cases.append((case,manifest,None))
        report["official_rtl"]={"repository":entry["repository"],"commit":entry["commit"],
                                "blobs":{p:entry["blobs"][p] for p in ALU_FILES}}
    try:
        for case,manifest,n in cases:
            samples=[]
            for i in range(repetitions):
                sample=case/f"sample_{i+1}"
                cmd=[sys.executable,"-m","scripts.run_scalability_pr55","--worker",
                     "--manifest",str(manifest),"--out",str(sample),"--timeout",str(timeout)]
                if n is not None:
                    cmd.extend(["--stages",str(n)])
                # Separate process bounds the entire Python + EDA pipeline.
                subprocess.run(cmd,check=True,timeout=timeout+120,cwd=ROOT)
                samples.append(json.loads((sample/"sample.json").read_text(encoding="utf-8")))
            report["cases"].append({"name":case.name,"stages":n,**summarize(samples)})
            save()
            print(f"{case.name}: {repetitions} samples passed",flush=True)
        if entry:
            verify_checkout(upstream,entry)
        report["status"]="passed"
    except Exception as exc:
        report["status"]="failed"
        report["error"]=str(exc)
        raise
    finally:
        save()
        print(f"Report: {report_path}",flush=True)
    return report_path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--sizes",nargs="+",type=int,default=DEFAULT_SIZES)
    parser.add_argument("--repetitions",type=int,default=3)
    parser.add_argument("--timeout",type=int,default=180)
    parser.add_argument("--synthetic-only",action="store_true")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--manifest",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--stages",type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args.manifest,args.out,args.timeout,args.stages)
    else:
        execute(args.out,args.sizes,args.repetitions,args.timeout,not args.synthetic_only)

if __name__=="__main__":
    main()
