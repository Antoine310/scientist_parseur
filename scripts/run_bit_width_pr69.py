"""PR69: explicit width conversion positions and independent value oracle."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from scripts.cv32e40p_pr67 import bit_inventory
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="bit_width_pr69"
FIXTURE=ROOT/"tests/fixtures/bit_width_pr69.sv"

def compare(old,new,instances):
    excluded={"bit_accesses","bit_dependency_graph","coverage","analysis_limits"}
    if {k:v for k,v in old.items() if k not in excluded}!={k:v for k,v in new.items() if k not in excluded}:
        raise ValueError("non-target graph changed")
    a,b=old["bit_dependency_graph"],new["bit_dependency_graph"]
    if len(a["items"])!=len(b["items"]) or b["counts"]["truncated"]:
        raise ValueError("assignment denominator changed or bit budget hit")
    old_edges=defaultdict(list)
    new_edges=defaultdict(list)
    for graph,bucket in ((a,old_edges),(b,new_edges)):
        for e in graph["edges"]:
            bucket[e["assignment_id"]].append(e)
    recovered=[]
    for i,(x,y) in enumerate(zip(a["items"],b["items"])):
        if (x["assignment_id"],x["target"],x["source_location"])!=(y["assignment_id"],y["target"],y["source_location"]):
            raise ValueError("assignment identity changed")
        if x["coverage"]!="partial":
            if x!=y or old_edges[i]!=new_edges[i]:
                raise ValueError("previously supported assignment changed")
        elif y["coverage"]!="partial":
            r=new["bit_accesses"]["items"][i]
            if not r.get("width_conversions"):
                raise ValueError("unexplained newly supported assignment")
            recovered.append({"assignment_id":i,"target":y["target"],"source":y["source_location"],
                "old_reason":old["bit_accesses"]["items"][i].get("reason") or x.get("reason"),
                "modes":r["width_conversions"],"new_edges":y["edge_count"],
                "constant_target_bits":y["constant_target_bits"]})
    if b["counts"]["supported"]-a["counts"]["supported"]!=len(recovered):
        raise ValueError("recovered count mismatch")
    return {"before":a["counts"],"after":b["counts"],"recovered":recovered,
            "recovered_by_reason":dict(Counter(r["old_reason"] for r in recovered)),
            "after_partial_reasons":bit_inventory(new,instances)["partial_reasons"]}

def check_fixture(graph):
    bits=graph["bit_dependency_graph"]
    expected={
        "zext":("u",[(i,i) for i in range(8)],list(range(8,12))),
        "sext":("s",[(i,i) for i in range(8)]+[(7,i) for i in range(8,12)],[]),
        "narrowed":("u",[(i,i) for i in range(4)],[]),
    }
    for target,(source,pairs,constants) in expected.items():
        rows=[r for r in bits["items"] if r["target"]==TOP+"."+target]
        assert len(rows)==1 and rows[0]["coverage"]!="partial",rows
        e=[e for e in bits["edges"] if e["target"]==TOP+"."+target]
        assert sorted((v["source"],v["source_bit"],v["target_bit"]) for v in e)==sorted(
            (TOP+"."+source,x,y) for x,y in pairs),e
        assert rows[0]["constant_target_bits"]==constants,rows
    return {"reviewed_edges":24,"constant_lanes":4,"behavioral_vectors":256}

def execute(out):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"bit_width.result.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        fixture,index=extract(run/"fixture",TOP,[FIXTURE])
        report["fixture"]=check_fixture(fixture)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.bit_width_pr69",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,baseline in [
            ("alu","cv32e40p_alu",d.parent/"alu",(479,254,225,477)),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",(1199,467,732,2842))]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_width_conversions=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx,enable_width_literals=False)
            c=old["bit_dependency_graph"]["counts"]
            assert tuple(c[k] for k in ("assignments","supported","partial","edges"))==baseline,c
            delta=compare(old,new,{i["path"]:i["module"] for i in idx["instances"]})
            report["cases"].append({"name":name,**delta})
            save()
            print(json.dumps({"name":name,**{k:v for k,v in delta.items() if k!="recovered"}},indent=2))
        if not report["cases"][1]["recovered"]:
            raise ValueError("no recovered core assignments")
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save()
        print(f"Report: {path}",flush=True)
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
