"""Actual SDK stdio on fresh PR93 CLI artifacts (no EDA in server)."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from rtlprep.member_query import load_member_graph, query_members, CATEGORIES
from rtlprep.mcp_data import MAX_MEMBER_RESPONSE_BYTES, MAX_GRAPH_BYTES
from scripts.run_member_cli_pr93 import execute as cli_reference
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


async def probe(folder,name,expected):
    from mcp import Client, StdioServerParameters
    gpath=folder/"rtl_dependencies.json"
    ipath=folder/"rtl_index.json"
    manifest=folder/"manifest_snapshot.json"
    paths=(gpath,ipath,manifest)
    before={p.name:sha(p) for p in paths}
    graph=load_member_graph(gpath)
    argv=["-m","rtlprep","mcp","--graph",str(gpath),"--index",str(ipath),
          "--manifest",str(manifest)]
    params=StdioServerParameters(command=sys.executable,args=argv)
    records=[]
    sizes=[]
    pages=0
    async with Client(params) as client:
        tools=await client.list_tools()
        names={tool.name for tool in tools.tools}
        assert "rtl_member_evidence" in names and len(names)==18,names
        assert not any(any(v in n for v in ("execute","write","delete","run")) for n in names)
        async def call(tool,**kwargs):
            response=await client.call_tool(tool,kwargs)
            assert not response.is_error,(tool,response)
            assert isinstance(response.structured_content,dict)
            return response.structured_content
        caps=await call("rtl_capabilities")
        assert caps["mode"]=="read_only_snapshot" and not caps["runs_eda"] and not caps["edits_files"]
        assert caps["source_snapshot_status"]=="matching"
        assert caps["member_evidence_available"]==(name!="fixture-default")
        assert caps["member_query_limits"]["graph_bytes"]==MAX_GRAPH_BYTES
        assert caps["member_query_limits"]["response_compact_json_bytes"]==MAX_MEMBER_RESPONSE_BYTES
        async def page(**kwargs):
            result=await call("rtl_member_evidence",**kwargs)
            expected_page=query_members(graph,**kwargs)
            assert result=={**expected_page,"origin":"stored_member_candidates_not_reexecuted",
                            "source_snapshot_status":"matching",
                            "artifact_fingerprint":graph["source_fingerprint"]}
            size=len(json.dumps(result,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode())
            assert size<=MAX_MEMBER_RESPONSE_BYTES
            sizes.append(size)
            return result
        offset=0
        while True:
            p=await page(limit=100,offset=offset)
            pages+=1
            records.extend(p["items"])
            if p["next_offset"] is None:
                break
            offset=p["next_offset"]
        assert len(records)==expected and len({r["record_id"] for r in records})==expected
        for cat in CATEGORIES:
            p=await page(category=cat,limit=20,offset=0)
            assert p["category_published"]==(name!="fixture-default")
        if name=="core":
            p=await page(category="nba_sampled",signal="cv32e40p_core.cs_registers_i.mstatus_q",limit=20,offset=0)
            assert p["total"]==2
            assert 32*1024*1024<gpath.stat().st_size<=MAX_GRAPH_BYTES
        for args in ({"limit":101},{"offset":-1},{"category":"not_a_category"},{"signal":"../.git/config"}):
            res=await client.call_tool("rtl_member_evidence",args)
            assert res.is_error,(args,res)
    assert before=={p.name:sha(p) for p in paths}
    return {"name":name,"records":expected,"pages":pages,"max_response_compact_bytes":max(sizes),
            "graph_bytes":gpath.stat().st_size,"input_sha256":before,"exact_query_match":True,
            "snapshot_unchanged":True,"protocol":"real_sdk_stdio","tools":len(names)}


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
    try:
        ref=cli_reference(run/"reference") if reference is None else reference.resolve()
        assert json.loads(ref.read_text())["status"]=="passed"
        for name,sub,n in (("fixture-default","fixture-0",0),("fixture","fixture-7",12),
                           ("alu","alu",0),("core","core",1481)):
            report["cases"].append(asyncio.run(asyncio.wait_for(probe(ref.parent/sub,name,n),timeout=120)))
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
