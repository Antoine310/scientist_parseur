"""Exercise actual CLI generation and read-only pages on pinned designs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from rtlprep.member_query import CHANNELS, query_members
from scripts.run_member_sequential_pr90 import check_channel
from scripts.run_member_benchmark_pr91 import historical_digest
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_scalability_pr55 import write_manifest
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
FLAGS=("--member-positions","--member-combinational","--member-sequential")
KEYS=tuple(CHANNELS)


def cli(*args):
    proc=subprocess.run([sys.executable,"-m","rtlprep",*map(str,args)],cwd=ROOT,
                        capture_output=True,text=True,timeout=180)
    if proc.returncode:
        raise RuntimeError(proc.stdout[-2000:]+proc.stderr[-2000:])
    return proc.stdout


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    path=run/"summary.json"
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,manifest,flags,enabled,folder):
        cli("deps",manifest,"--out",folder,"--timeout",180,*flags)
        gpath=folder/"rtl_dependencies.json"
        graph=json.loads(gpath.read_text())
        idx=json.loads((folder/"rtl_index.json").read_text())
        ast=read_ast(folder/"elaborated_ast.json")
        options=dict(zip(("enable_member_positions","enable_member_combinational","enable_member_sequential"),enabled))
        api=build_dependency_graph(ast,expected_top=idx["top"],index=idx,**options)
        assert {k:v for k,v in graph.items() if k!="source_fingerprint"}==json.loads(json.dumps(api))
        assert {k for k in KEYS if k in graph}=={k for k,e in zip(KEYS,enabled) if e}
        baseline=build_dependency_graph(ast,expected_top=idx["top"],index=idx)
        assert historical_digest(graph)==historical_digest(baseline)
        result=json.loads((folder/"deps.result.json").read_text())
        assert result["status"]=="passed"
        if any(enabled):
            assert result["member_evidence"]==query_members(graph)["channels"]
        else:
            assert "member_evidence" not in result
        pages=[]
        offset=0
        while True:
            page=json.loads(cli("member-evidence",gpath,"--limit",100,"--offset",offset))
            assert page==query_members(graph,limit=100,offset=offset)
            pages.extend(page["items"])
            if page["next_offset"] is None:
                break
            offset=page["next_offset"]
        assert len(pages)==page["total"] and len({r["record_id"] for r in pages})==len(pages)
        if all(enabled):
            check_channel(graph[KEYS[2]],graph[KEYS[0]],graph[KEYS[1]],name)
        if name=="core":
            filtered=json.loads(cli("member-evidence",gpath,"--category","nba_sampled",
                "--signal","cv32e40p_core.cs_registers_i.mstatus_q"))
            assert filtered["total"]==2 and filtered["category_published"]
        report["cases"].append({"name":name,"flags":list(flags),"enabled":list(enabled),
            "records":len(pages),"bytes":gpath.stat().st_size,"channels":page["channels"],
            "api_exact_match":True,"historical_unchanged":True,"pagination_exact":True})
        save()
    try:
        fixture=run/"design.json"
        top="member_pattern_pr84"
        write_manifest(fixture,top,[ROOT/"tests/fixtures"/(top+".sv")])
        for mask in range(8):
            enabled=tuple(bool(mask&(1<<i)) for i in range(3))
            flags=tuple(f for f,e in zip(FLAGS,enabled) if e)
            case(top,fixture,flags,enabled,run/f"fixture-{mask}")
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        for name,folder in (("alu",d.parent/"alu"),("core",Path(ref["core_reference_report"]).parent/"static")):
            manifest=(folder if name=="alu" else folder.parent)/"design.json"
            case(name,manifest,("--member-all",),(True,True,True),run/name)
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
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
