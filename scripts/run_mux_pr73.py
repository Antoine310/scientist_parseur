"""PR73 — same-AST mux candidates with compact validation summary."""
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
from scripts.run_bitwise_pr72 import edge_key

ROOT=Path(__file__).resolve().parents[1]
TOP="mux_pr73"
FIXTURE=ROOT/"tests/fixtures/mux_pr73.sv"

def keys(edges,role,identity):
    field="branch_id" if role=="mux_data_candidate" else "decision_id"
    return {edge_key(e) for e in edges if e["relation"]==role and e[field]==identity}

def validate_row(row,edges):
    decisions,branches=row["decisions"],row["branches"]
    assert [d["decision_id"] for d in decisions]==list(range(len(decisions)))
    assert [b["branch_id"] for b in branches]==list(range(len(branches)))
    assert len(decisions)>=1 and len(branches)==len(decisions)+1
    assert decisions[0]["path"]==[]
    def path_key(path):
        return tuple((p["decision_id"],p["arm"]) for p in path)
    paths={path_key(d["path"]) for d in decisions}
    leaf_paths={path_key(b["path"]) for b in branches}
    expected={path_key(d["path"])+((d["decision_id"],arm),)
              for d in decisions for arm in ("true","false")}
    assert len(paths)==len(decisions) and len(leaf_paths)==len(branches)
    assert not paths&leaf_paths and (paths|leaf_paths)-{()}==expected
    dest=lambda e:(e["target"],tuple(e["target_packed_indices"]),e["target_bit"])
    identities=[]
    for e in edges:
        role=e["relation"]
        assert role in ("mux_data_candidate","mux_control_candidate")
        field="branch_id" if role=="mux_data_candidate" else "decision_id"
        cap=len(branches) if field=="branch_id" else len(decisions)
        assert type(e[field]) is int and 0<=e[field]<cap
        identities.append((role,e[field],edge_key(e)))
    assert len(set(identities))==len(edges)
    target_sets=[]
    for b in branches:
        i=b["branch_id"]
        dynamic={dest(e) for e in edges if e["relation"]=="mux_data_candidate" and e["branch_id"]==i}
        fixed=[dest(e) for e in b["constant_target_positions"]]
        assert len(fixed)==len(set(fixed)) and not dynamic&set(fixed)
        target_sets.append(dynamic|set(fixed))
    assert target_sets[0] and all(t==target_sets[0] for t in target_sets)
    assert all(t[0]==row["target"] for t in target_sets[0])
    for d in decisions:
        local=[e for e in edges if e["relation"]=="mux_control_candidate" and e["decision_id"]==d["decision_id"]]
        sources={(e["source"],tuple(e["source_packed_indices"]),e["source_bit"]) for e in local}
        assert len(sources)==d["control_source_count"]
        assert len(local)==len(sources)*len(target_sets[0])
        assert not local or {dest(e) for e in local}==target_sets[0]

def check_fixture(graph):
    data=graph["mux_dependencies"]
    assert data["counts"]=={"captured":5,"supported":5,"partial":0,"edges":64,"truncated":False},data["counts"]
    expected={
        "y":([("a",()),("b",())],[("s",0)],[]),
        "y_nested":([("a",()),("b",()),None],[("s",0),("t",0)],[2]),
        "y_cmp":([("a",()),("b",())],[("a",0),("b",0)],[]),
        "y_packed":([("p",(1,)),("p",(0,))],[("s",0)],[]),
        "y_const":([("a",()),None],[("t",0)],[1]),
    }
    for name,(sources,ctrl,constant_ids) in expected.items():
        target=TOP+"."+name
        match=[(i,r) for i,r in enumerate(data["items"]) if r["target"]==target]
        assert len(match)==1,match
        i,row=match[0]
        local=[e for e in data["edges"] if e["assignment_id"]==i]
        validate_row(row,local)
        for j,src in enumerate(sources):
            want=set() if src is None else {(TOP+"."+src[0],src[1],b,target,(),b) for b in range(4)}
            assert keys(local,"mux_data_candidate",j)==want,(name,j)
        if name=="y_nested":
            for j,(src,sbit) in enumerate(ctrl):
                assert keys(local,"mux_control_candidate",j)=={(TOP+"."+src,(),sbit,target,(),b) for b in range(4)}
            assert row["decisions"][1]["path"]==[{"decision_id":0,"arm":"true"}]
        else:
            assert keys(local,"mux_control_candidate",0)=={(TOP+"."+src,(),sbit,target,(),b) for src,sbit in ctrl for b in range(4)}
        for b in row["branches"]:
            j=b["branch_id"]
            assert [p["target_bit"] for p in b["constant_target_positions"]]==(list(range(4)) if j in constant_ids else [])
    return {"assignments":5,"data_candidates":36,"control_candidates":28,
            "branch_constant_positions":8,"decisions":6,"branches":11,
            "behavioral_vectors":1024,"behavioral_checks":5120}

def compare(old,new,instances):
    excluded={"mux_dependencies","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={k:v for k,v in new.items() if k not in excluded},"non-mux graph changed"
    assert not old["mux_dependencies"]["items"]
    flat=new["bit_dependency_graph"]["items"]
    arrays={r["flat_assignment_id"] for r in new["array_dependencies"]["items"]
            if r.get("coordinate_evidence")=="pr71_fixed_packed" and r["coverage"]!="partial"
            and flat[r["flat_assignment_id"]]["coverage"]=="partial"}
    logical={r["flat_assignment_id"] for r in new["bitwise_dependencies"]["items"] if r["coverage"]!="partial"}
    previous=arrays|logical
    data=new["mux_dependencies"]
    by=defaultdict(list)
    for e in data["edges"]:
        i=e["assignment_id"]
        assert type(i) is int and 0<=i<len(data["items"])
        by[i].append(e)
    seen=set()
    recovered=[]
    reasons=Counter()
    for i,r in enumerate(data["items"]):
        ordinal=r["flat_assignment_id"]
        assert type(ordinal) is int and 0<=ordinal<len(flat) and ordinal not in seen
        seen.add(ordinal)
        f=flat[ordinal]
        assert f["coverage"]=="partial" and f["target"]==r["target"] and f.get("source_location")==r.get("source_location")
        local=by[i]
        assert r["edge_count"]==len(local) and all(e["target"]==r["target"] for e in local)
        if r["coverage"]=="partial":
            assert not local and "decisions" not in r and "branches" not in r
            reasons[r["reason"]]+=1
            continue
        validate_row(r,local)
        recovered.append({"flat_assignment_id":ordinal,"target":r["target"],
            "instance":owner_for(r["target"],instances),"source_location":r["source_location"],
            "already_supported":ordinal in previous,"decisions":r["decisions"],
            "branches":r["branches"],"edges":local})
    extra=[r for r in recovered if not r["already_supported"]]
    total=new["bit_dependency_graph"]["counts"]["assignments"]
    combined=new["bit_dependency_graph"]["counts"]["supported"]+len(previous)+len(extra)
    assert combined<=total and len(recovered)==data["counts"]["supported"] and not data["counts"]["truncated"]
    return {"flat_counts":new["bit_dependency_graph"]["counts"],
            "array_counts":new["array_dependencies"]["counts"],"bitwise_counts":new["bitwise_dependencies"]["counts"],
            "mux_counts":data["counts"],"previous_linked_support":len(previous),
            "new_unique_supported_assignments":len(extra),"overlap_with_previous":len(recovered)-len(extra),
            "minimum_combined_supported":combined,"remaining_without_linked_support":total-combined,
            "new_data_candidates":sum(e["relation"]=="mux_data_candidate" for r in extra for e in r["edges"]),
            "new_control_candidates":sum(e["relation"]=="mux_control_candidate" for r in extra for e in r["edges"]),
            "new_branch_constant_positions":sum(len(b["constant_target_positions"]) for r in extra for b in r["branches"]),
            "new_by_instance":dict(Counter(r["instance"] for r in extra)),
            "remaining_mux_reasons":dict(reasons),"recovered":recovered}

def check_alu_oracle(delta,owner):
    target=owner+".result_o"
    match=[r for r in delta["recovered"] if r["target"]==target
           and (r["source_location"] or {}).get("line")==961]
    assert len(match)==1,match
    r=match[0]
    expected_true={(owner+("."+"operand_a_i" if b<16 else ".adder_result"),(),b,target,(),b) for b in range(32)}
    expected_false={(owner+".result_minmax",(),b,target,(),b) for b in range(32)}
    expected_control={(owner+".is_clpx_i",(),0,target,(),b) for b in range(32)}
    assert len(r["edges"])==96
    assert keys(r["edges"],"mux_data_candidate",0)==expected_true
    assert keys(r["edges"],"mux_data_candidate",1)==expected_false
    assert keys(r["edges"],"mux_control_candidate",0)==expected_control
    assert [b["path"] for b in r["branches"]]==[[{"decision_id":0,"arm":"true"}],[{"decision_id":0,"arm":"false"}]]
    return {"status":"passed","source_line":961,"data_candidates":64,"control_candidates":32}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"mux.result.json"
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.mux_pr73",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,flat_baseline,array_baseline,bw_baseline,linked,owner in [
            ("alu","cv32e40p_alu",d.parent/"alu",(479,254,225,477),(130,61,69,21),(43,8,35,74),36,"cv32e40p_alu"),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             (1199,531,668,2842),(378,245,133,2469),(66,24,42,375),175,"cv32e40p_core.ex_stage_i.alu_i")]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_dynamic=False,enable_mux=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx,enable_dynamic=False)
            for channel,expected in (("bit_dependency_graph",flat_baseline),
                    ("array_dependencies",array_baseline),("bitwise_dependencies",bw_baseline)):
                c=old[channel]["counts"]
                k="assignments" if channel=="bit_dependency_graph" else "captured"
                assert tuple(c[x] for x in (k,"supported","partial","edges"))==expected,(channel,c)
            delta=compare(old,new,{i["path"]:i["module"] for i in idx["instances"]})
            assert delta["previous_linked_support"]==linked
            case={"name":name,**delta,"truncated_analyzers":new["analysis_limits"]["truncated_analyzers"]}
            report["cases"].append(case)
            save()
            case["alu_oracle"]=check_alu_oracle(delta,owner)
            assert case["new_unique_supported_assignments"]>0
            assert not case["truncated_analyzers"],case["truncated_analyzers"]
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
