"""PR70: typed literal and width retries with exact PR69 regression baseline."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from scripts.cv32e40p_pr67 import owner_for
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_bit_width_pr69 import compare
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="bit_width_pr70"
FIXTURE=ROOT/"tests/fixtures/bit_width_pr70.sv"

def check_fixture(graph):
    bits=graph["bit_dependency_graph"]
    expected={
        "ones":([],list(range(8))),
        "zeroes":([],list(range(8))),
        "mixed":([(i,i+2) for i in range(4)],[0,1]),
    }
    for target,(pairs,constants) in expected.items():
        rows=[r for r in bits["items"] if r["target"]==TOP+"."+target]
        assert len(rows)==1 and rows[0]["coverage"]!="partial",rows
        edges=[e for e in bits["edges"] if e["target"]==TOP+"."+target]
        assert sorted((e["source"],e["source_bit"],e["target_bit"]) for e in edges)==sorted(
            (TOP+".u",a,b) for a,b in pairs),edges
        assert rows[0]["constant_target_bits"]==constants,rows
    flags=[r for r in bits["items"] if r["target"]==TOP+".flags"]
    assert len(flags)==3,flags
    assert all(r["coverage"]!="partial" and r["edge_count"]==0 for r in flags),flags
    assert sorted(r["constant_target_bits"] for r in flags)==[[0],[1],[2]],flags
    return {"reviewed_edges":4,"constant_lanes":21,"behavioral_vectors":256,
            "behavioral_checks":1024,"generated_constant_assignments":3}

def recovery_summary(delta,instances):
    rows=delta["recovered"]
    return {"by_instance":dict(Counter(owner_for(r["target"],instances) for r in rows)),
            "modes":dict(Counter(e["mode"] for r in rows for e in r["modes"])),
            "new_dynamic_edges":sum(r["new_edges"] for r in rows),
            "new_constant_lanes":sum(len(r["constant_target_bits"]) for r in rows)}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"bit_width_literals.result.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        fixture,_=extract(run/"fixture",TOP,[FIXTURE])
        report["fixture"]=check_fixture(fixture)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.bit_width_pr70",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,baseline,legacy in [
            ("alu","cv32e40p_alu",d.parent/"alu",(479,254,225,477),(479,254,225,477)),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             (1199,528,671,2842),(1199,467,732,2842))]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            instances={i["path"]:i["module"] for i in idx["instances"]}
            first=build_dependency_graph(ast,expected_top=top,index=idx,enable_width_conversions=False)
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_width_literals=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx)
            for graph,expected in ((first,legacy),(old,baseline)):
                c=graph["bit_dependency_graph"]["counts"]
                assert tuple(c[k] for k in ("assignments","supported","partial","edges"))==expected,c
            original=compare(first,old,instances)
            delta=compare(old,new,instances)
            case={"name":name,**delta,"pr69_recovery_summary":recovery_summary(original,instances),
                  "pr70_recovery_summary":recovery_summary(delta,instances),
                  "truncated_analyzers":new["analysis_limits"]["truncated_analyzers"]}
            if name=="core":
                # Independent expected positions read from the pinned source
                # and actual elaboration: mcountinhibit_q scalar vector,
                # disabled/reserved counters at indices 0, 2, 3.
                csr=[r for r in delta["recovered"]
                     if r["target"]=="cv32e40p_core.cs_registers_i.mcountinhibit_q"
                     and r["source"] and r["source"].get("line")==1529]
                expected=[[0],[2],[3]]
                assert sorted(r["constant_target_bits"] for r in csr)==expected,csr
                assert all(r["new_edges"]==0 and any(m["mode"]=="scoped_procedural_selectors"
                           for m in r["modes"]) for r in csr),csr
                case["csr_genvar_oracle"]={"expected":expected,"observed":expected,"status":"passed"}
            report["cases"].append(case)
            save()
            print(json.dumps({k:v for k,v in case.items() if k!="recovered"},indent=2),flush=True)
        if not any(c["recovered"] for c in report["cases"]):
            raise ValueError("no additional official assignment recovered")
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
