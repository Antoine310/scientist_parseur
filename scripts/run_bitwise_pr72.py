"""PR72: separate syntactic bitwise candidates and compact same-AST report."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from scripts.cv32e40p_pr67 import owner_for
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="bitwise_pr72"
FIXTURE=ROOT/"tests/fixtures/bitwise_pr72.sv"

def check_fixture(graph):
    data=graph["bitwise_dependencies"]
    assert data["counts"]=={"captured":7,"supported":7,"partial":0,"edges":48,"truncated":False},data
    expected=set()
    for target in ("y_and","y_or","y_xor","y_xnor"):
        expected.update((TOP+"."+s,(),i,TOP+"."+target,(),i) for s in ("a","b") for i in range(4))
    expected.update((TOP+".p",(w,),i,TOP+".y_packed",(),i) for w in (0,1) for i in range(4))
    expected.update((TOP+".a",(),i,TOP+".y_mask",(),i) for i in range(4))
    expected.update((TOP+".a",(),i,TOP+".parity",(),0) for i in range(4))
    actual={edge_key(e) for e in data["edges"]}
    assert actual==expected and len(actual)==len(data["edges"]),{"missing":sorted(expected-actual),"unexpected":sorted(actual-expected)}
    assert all(e["relation"]=="syntactic_influence_candidate" for e in data["edges"])
    assert all(not r["constant_target_positions"] for r in data["items"])
    return {"reviewed_candidate_edges":48,"assignments":7,"behavioral_vectors":256,
            "behavioral_checks":1792,"masked_output_always_zero_but_candidate_edges_retained":True}

def edge_key(e):
    return (e["source"],tuple(e["source_packed_indices"]),e["source_bit"],
            e["target"],tuple(e["target_packed_indices"]),e["target_bit"])

def compare(old,new,instances):
    excluded={"bitwise_dependencies","analysis_limits"}
    if {k:v for k,v in old.items() if k not in excluded}!={k:v for k,v in new.items() if k not in excluded}:
        raise ValueError("non-bitwise graph changed")
    assert not old["bitwise_dependencies"]["items"]
    data=new["bitwise_dependencies"]
    flat=new["bit_dependency_graph"]["items"]
    previous={r["flat_assignment_id"] for r in new["array_dependencies"]["items"]
              if r.get("coordinate_evidence")=="pr71_fixed_packed" and r["coverage"]!="partial"
              and flat[r["flat_assignment_id"]]["coverage"]=="partial"}
    by=defaultdict(list)
    for e in data["edges"]:
        i=e["assignment_id"]
        if type(i) is not int or not 0<=i<len(data["items"]):
            raise ValueError("invalid bitwise assignment ID")
        by[i].append(e)
    seen=set()
    recovered=[]
    reasons=Counter()
    for i,r in enumerate(data["items"]):
        ordinal=r["flat_assignment_id"]
        if type(ordinal) is not int or not 0<=ordinal<len(flat) or ordinal in seen:
            raise ValueError("invalid or repeated flat link")
        seen.add(ordinal)
        f=flat[ordinal]
        if f["coverage"]!="partial" or f["target"]!=r["target"] or f.get("source_location")!=r.get("source_location"):
            raise ValueError("invalid flat partial identity")
        edges=by[i]
        fixed=r.get("constant_target_positions",[])
        if len(edges)!=r["edge_count"] or any(e["target"]!=r["target"] for e in edges+fixed):
            raise ValueError("invalid target or edge count")
        if len({edge_key(e) for e in edges})!=len(edges):
            raise ValueError("duplicate candidate edge")
        if any(e["relation"]!="syntactic_influence_candidate" for e in edges):
            raise ValueError("candidate mislabeled")
        if r["coverage"]=="partial":
            if edges or fixed:
                raise ValueError("partial assignment emitted candidates")
            reasons[r["reason"]]+=1
            continue
        if not edges and not fixed:
            raise ValueError("empty supported candidate row")
        recovered.append({"flat_assignment_id":ordinal,"target":r["target"],
            "source_location":r["source_location"],"instance":owner_for(r["target"],instances),
            "operators":r["operators"],"already_supported_by_pr71":ordinal in previous,
            "edges":edges,"constant_positions":fixed})
    extra=[r for r in recovered if not r["already_supported_by_pr71"]]
    nflat=new["bit_dependency_graph"]["counts"]["supported"]
    total=new["bit_dependency_graph"]["counts"]["assignments"]
    union=nflat+len(previous)+len(extra)
    if union>total or len(recovered)!=data["counts"]["supported"] or data["counts"]["truncated"]:
        raise ValueError("inconsistent support or budget hit")
    return {"flat_counts":new["bit_dependency_graph"]["counts"],
            "array_counts":new["array_dependencies"]["counts"],
            "bitwise_counts":data["counts"],"pr71_linked_support":len(previous),
            "new_unique_supported_assignments":len(extra),"overlap_with_pr71":len(recovered)-len(extra),
            "minimum_combined_supported":union,"remaining_without_linked_support":total-union,
            "new_candidate_edges":sum(len(r["edges"]) for r in extra),
            "new_constant_positions":sum(len(r["constant_positions"]) for r in extra),
            "new_by_instance":dict(Counter(r["instance"] for r in extra)),
            "new_by_operator":dict(Counter(op for r in extra for op in r["operators"])),
            "remaining_bitwise_reasons":dict(reasons),"recovered":recovered}

def check_alu_oracle(delta,owner):
    target=owner+".div_op_a_signed"
    rows=[r for r in delta["recovered"] if r["target"]==target
          and (r.get("source_location") or {}).get("line")==889]
    assert len(rows)==1,rows
    r=rows[0]
    expected={(owner+".operand_a_i",(),31,target,(),0),
              (owner+".div_signed",(),0,target,(),0)}
    assert {edge_key(e) for e in r["edges"]}==expected and len(r["edges"])==2,r
    assert r["operators"]==["BinaryAnd"] and not r["constant_positions"],r
    return {"status":"passed","source_line":889,"candidate_edges":2}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"bitwise.result.json"
    summary=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        compact={**report,"cases":[{k:v for k,v in c.items() if k!="recovered"} for c in report["cases"]]}
        summary.write_text(json.dumps(compact,indent=2),encoding="utf-8")
    save()
    try:
        fixture,_=extract(run/"fixture",TOP,[FIXTURE])
        report["fixture"]=check_fixture(fixture)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.bitwise_pr72",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,flat_baseline,array_baseline,linked,owner in [
            ("alu","cv32e40p_alu",d.parent/"alu",(479,254,225,477),(130,61,69,21),28,"cv32e40p_alu"),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             (1199,531,668,2842),(378,245,133,2469),151,"cv32e40p_core.ex_stage_i.alu_i")]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_bitwise=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx)
            c=old["bit_dependency_graph"]["counts"]
            assert tuple(c[k] for k in ("assignments","supported","partial","edges"))==flat_baseline,c
            c=old["array_dependencies"]["counts"]
            assert tuple(c[k] for k in ("captured","supported","partial","edges"))==array_baseline,c
            delta=compare(old,new,{i["path"]:i["module"] for i in idx["instances"]})
            assert delta["pr71_linked_support"]==linked,delta["pr71_linked_support"]
            case={"name":name,**delta,"truncated_analyzers":new["analysis_limits"]["truncated_analyzers"]}
            case["alu_oracle"]=check_alu_oracle(delta,owner)
            assert case["new_unique_supported_assignments"]>0,case
            assert not case["truncated_analyzers"],case["truncated_analyzers"]
            report["cases"].append(case)
            save()
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(f"Summary: {summary}",flush=True)
        print(f"Detailed report: {path}",flush=True)
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
