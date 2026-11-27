"""Real CLI publication and MCP stdio parity, including pinned independent RTL."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from rtlprep.census_query import load_report,query_census,file_sha,INPUTS
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.cv32e40p_pr67 import ast_inventory
from rtlprep.analysis_budgets import read_ast

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"tests/fixtures/capture_audit_pr102.sv"


def cli(*args):
    p=subprocess.run([sys.executable,"-m","rtlprep",*map(str,args)],cwd=ROOT,
                     capture_output=True,text=True,timeout=180)
    if p.returncode:
        raise ValueError("CLI failure: "+p.stderr[-2000:])
    return json.loads(p.stdout)


async def protocol(path,folder,report):
    from mcp import Client,StdioServerParameters
    args=["-m","rtlprep","mcp","--selection-census",str(path),
          "--index",str(folder/INPUTS[1]),"--graph",str(folder/INPUTS[2])]
    async with Client(StdioServerParameters(command=sys.executable,args=args)) as client:
        names={t.name for t in (await client.list_tools()).tools}
        assert "rtl_selection_census" in names and len(names)==19,names
        async def call(tool,**kwargs):
            response=await client.call_tool(tool,kwargs)
            assert not response.is_error,(tool,response)
            return response.structured_content
        caps=await call("rtl_capabilities")
        assert caps["selection_census_versions"]==[1,2] and not caps["runs_eda"] and not caps["edits_files"]
        assert caps["top"]==report["top"]
        pages=0
        for version in (1,2):
            offset=0
            found=[]
            while True:
                params={"version":version,"classification":"captured","limit":100,"offset":offset}
                p=await call("rtl_selection_census",**params)
                assert p==query_census(report,**params)
                found.extend(p["items"])
                pages+=1
                if p["next_offset"] is None: break
                offset=p["next_offset"]
            assert len(found)==report["counts"]["v"+str(version)]["captured"]
        for bad in ({"version":3},{"version":2,"limit":101},{"version":2,"offset":-1},{}):
            assert (await client.call_tool("rtl_selection_census",bad)).is_error
    return pages


def execute(out,reference=None):
    out=out.resolve()
    lock=load_lock()
    for e in lock:
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    summary=run/"summary.json"
    result={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_applicable_to_syntax_publication"}
    def save(): summary.write_text(json.dumps(result,indent=2))
    save()
    def case(name,folder,expected=None,upstream=None):
        before={k:file_sha(folder/k) for k in INPUTS}
        path=run/(name+".selection-census.json")
        published=cli("selection-census-build",folder,"--out",path)
        report=load_report(path)
        assert published["input_sha256"]==before==report["input_sha256"]
        g=json.loads((folder/INPUTS[2]).read_text())
        idx=json.loads((folder/INPUTS[1]).read_text())
        ast=read_ast(folder/INPUTS[0])
        prior=ast_inventory(ast,{r["path"]:r["module"] for r in idx["instances"]})
        a,b=report["counts"]["v1"],report["counts"]["v2"]
        assert a["ast_occurrences"]==b["ast_occurrences"]==prior["assignment_count"]
        assert a["captured"]==g["bit_dependency_graph"]["counts"]["assignments"]
        assert a["position_supported"]==b["position_supported"]==g["bit_dependency_graph"]["counts"]["supported"]
        assert b["captured"]-a["captured"]==report["new_partial_rows"] and report["new_edges"]==0
        if expected is not None:
            assert (a["ast_occurrences"],a["captured"],b["captured"])==expected
        for version in (1,2):
            p=cli("selection-census",path,"--version",version,"--classification","captured","--limit",1)
            assert p==query_census(report,version=version,classification="captured",limit=1)
        published_sha=file_sha(path)
        pages=asyncio.run(asyncio.wait_for(protocol(path,folder,report),timeout=120))
        assert before=={k:file_sha(folder/k) for k in INPUTS} and file_sha(path)==published_sha
        result["cases"].append({"name":name,"status":"passed","counts":report["counts"],"added":report["new_partial_rows"],
            "new_edges":0,"report_sha256":published_sha,"input_sha256":before,"real_mcp_pages":pages,
            "cli_mcp_exact":True,"historical_unchanged":True,"upstream":upstream})
        save()
    try:
        extract(run/"fixture","capture_audit_pr102",[FIXTURE])
        case("fixture",run/"fixture",(3,1,2))
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu",(612,479,479))
        case("core",Path(d["core_reference_report"]).parent/"static",(3811,1199,1212))
        for e in lock:
            if e["repository"] not in ("alexforencich/verilog-axis","ZipCPU/wbuart32"):
                continue
            root=ROOT/e["destination"]
            verify_checkout(root,e)
            for src in e["blobs"]:
                name=Path(src).stem
                folder=run/name
                extract(folder,name,[root/src])
                case(name,folder,upstream={"repository":e["repository"],"commit":e["commit"],"blob":e["blobs"][src]})
            verify_checkout(root,e)
        assert len(result["cases"])==6
        result["status"]="passed"
    except Exception as exc:
        result.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:3000])
        raise
    finally:
        save()
        print(summary.read_text(),flush=True)
        print(f"Summary: {summary}",flush=True)
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--reference",type=Path)
    a=p.parse_args()
    execute(a.out,a.reference)
