"""PR75 — lexical selector recovery with frozen previous channels and tree oracle."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from rtlprep.selector_recovery import constant_positions
from scripts.cv32e40p_pr67 import owner_for
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock
from scripts.run_mux_pr73 import validate_row, keys
from scripts.run_bitwise_pr72 import edge_key

ROOT=Path(__file__).resolve().parents[1]
TOP="selector_recovery_pr75"
FIXTURE=ROOT/"tests/fixtures/selector_recovery_pr75.sv"
CHANNELS=("bit_dependency_graph","array_dependencies","bitwise_dependencies",
          "mux_dependencies","dynamic_dependencies")

def destination(p):
    return p["target"],tuple(p["target_packed_indices"]),p["target_bit"]

def key(src,sp,sbit,dst,dp,dbit):
    return src,tuple(sp),sbit,dst,tuple(dp),dbit

def validate(row,edges):
    proofs=row["selector_proofs"]
    assert proofs and len({tuple(p["ast_path"]) for p in proofs})==len(proofs)
    assert all(p["evidence"]=="bounded_lexical_power" and type(p["index"]) is int
               and 0<=p["index"]<=1024 and p["ast_path"][-1] in ("selector","left","right")
               and "type" in p for p in proofs)
    if row["mode"]=="mux":
        validate_row(row,edges)
    else:
        assert row["mode"] in ("fixed","bitwise")
        role="fixed_position_candidate" if row["mode"]=="fixed" else "syntactic_influence_candidate"
        assert all(e["relation"]==role for e in edges)
        assert len({edge_key(e) for e in edges})==len(edges)
        fixed=[destination(p) for p in row["constant_target_positions"]]
        assert len(set(fixed))==len(fixed)
        assert not set(fixed)&{destination(e) for e in edges}
    assert edges or constant_positions(row)
    assert all(p["target"]==row["target"] for p in [*edges,*constant_positions(row)])

def check_fixture(graph):
    data=graph["selector_recovery"]
    assert data["counts"]=={"captured":5,"supported":5,"partial":0,"edges":28,"truncated":False},data
    seen=set()
    for i,row in enumerate(data["items"]):
        edges=[e for e in data["edges"] if e["assignment_id"]==i]
        validate(row,edges)
        t=row["target"]
        target_proof=[p for p in row["selector_proofs"] if p["ast_path"]==["left","selector"]]
        assert len(target_proof)==1,row
        g=target_proof[0]["index"]
        seen.add((t,g))
        if t==TOP+".y":
            assert row["mode"]=="bitwise"
            assert {edge_key(e) for e in edges}=={
                key(TOP+"."+s,(),g,t,(),g) for s in ("a","b")}
        elif t==TOP+".words":
            assert row["mode"]=="mux"
            assert keys(edges,"mux_data_candidate",0)=={key(TOP+".p",(g,),b,t,(g,),b) for b in range(4)}
            assert keys(edges,"mux_data_candidate",1)=={key(TOP+".q",(g,),b,t,(g,),b) for b in range(4)}
            assert keys(edges,"mux_control_candidate",0)=={key(TOP+".s",(),g,t,(g,),b) for b in range(4)}
        else:
            assert t==TOP+".fixed_out" and g==1 and row["mode"]=="fixed" and not edges
            assert [destination(p) for p in constant_positions(row)]==[(t,(),1)]
    assert seen=={(TOP+".y",0),(TOP+".y",1),(TOP+".words",0),(TOP+".words",1),(TOP+".fixed_out",1)}
    return {"assignments":5,"bitwise_candidates":4,"mux_data_candidates":16,
            "mux_control_candidates":8,"constant_positions":1,"behavioral_vectors":1024,
            "behavioral_checks":3072}

def compare(old,new,instances):
    excluded={"selector_recovery","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={
        k:v for k,v in new.items() if k not in excluded},"previous graph changed"
    assert not old["selector_recovery"]["items"]
    flat=new[CHANNELS[0]]["items"]
    previous={r["flat_assignment_id"] for name in CHANNELS[1:] for r in new[name]["items"]
              if "flat_assignment_id" in r and r["coverage"]!="partial"
              and flat[r["flat_assignment_id"]]["coverage"]=="partial"}
    eligible={r["flat_assignment_id"] for r in new["dynamic_dependencies"]["items"]
              if r["coverage"]=="partial" and r.get("reason")=="unproven_selector_type"}
    data=new["selector_recovery"]
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
        assert type(ordinal) is int and ordinal in eligible and ordinal not in seen
        seen.add(ordinal)
        f=flat[ordinal]
        assert f["coverage"]=="partial" and f["target"]==r["target"] and f.get("source_location")==r.get("source_location")
        edges=by[i]
        assert len(edges)==r["edge_count"]
        if r["coverage"]=="partial":
            assert not edges and "selector_proofs" not in r
            reasons[r["reason"]]+=1
            continue
        validate(r,edges)
        recovered.append({**r,"edges":edges,"instance":owner_for(r["target"],instances),
                          "already_supported":ordinal in previous})
    assert seen==eligible and len(recovered)==data["counts"]["supported"]
    extra=[r for r in recovered if not r["already_supported"]]
    total=new[CHANNELS[0]]["counts"]["assignments"]
    combined=new[CHANNELS[0]]["counts"]["supported"]+len(previous)+len(extra)
    assert combined<=total and not data["counts"]["truncated"]
    return {"previous_counts":{name:new[name]["counts"] for name in CHANNELS},
            "selector_recovery_counts":data["counts"],"previous_linked_support":len(previous),
            "new_unique_supported_assignments":len(extra),"overlap_with_previous":len(recovered)-len(extra),
            "minimum_combined_supported":combined,"remaining_without_linked_support":total-combined,
            "new_candidates_by_relation":dict(Counter(e["relation"] for r in extra for e in r["edges"])),
            "new_constant_positions":sum(len(constant_positions(r)) for r in extra),
            "new_by_instance":dict(Counter(r["instance"] for r in extra)),
            "new_by_mode":dict(Counter(r["mode"] for r in extra)),
            "remaining_reasons":dict(reasons),"recovered":recovered}

def check_tree(delta,owner):
    """Independent source-derived perfect binary tree oracle, LEN=32."""
    want={(57,31)}
    want.update((line,i) for line in (63,64) for i in range(15))
    want.update((line,i) for line in (73,74) for i in range(15,31))
    seen=set()
    for r in delta["recovered"]:
        assert r["instance"]==owner and not r["already_supported"],r
        line=r["source_location"]["line"]
        ps=[p for p in r["selector_proofs"] if p["ast_path"]==["left","selector"]]
        assert len(ps)==1,r
        i=ps[0]["index"]
        assert (line,i) in want and (line,i) not in seen,r
        seen.add((line,i))
        target=owner+(".sel_nodes" if line in (57,63,73) else ".index_nodes")
        assert r["target"]==target,r
        edges=r["edges"]
        if line==57:
            assert r["mode"]=="fixed" and not edges
            assert [destination(p) for p in constant_positions(r)]==[(target,(),31)]
            continue
        left=2*i+1 if i<15 else 2*(i-15)
        right=left+1
        ctrl=owner+(".sel_nodes" if i<15 else ".in_i")
        word=owner+(".index_nodes" if i<15 else ".index_lut")
        if line in (63,73):
            assert r["mode"]=="bitwise" and r["operators"]==["BinaryOr"]
            assert {edge_key(e) for e in edges}=={key(ctrl,(),j,target,(),i) for j in (left,right)}
            assert len(edges)==2 and not constant_positions(r)
        else:
            assert r["mode"]=="mux" and len(edges)==15 and not constant_positions(r)
            assert keys(edges,"mux_data_candidate",0)=={key(word,(left,),b,target,(i,),b) for b in range(5)}
            assert keys(edges,"mux_data_candidate",1)=={key(word,(right,),b,target,(i,),b) for b in range(5)}
            assert keys(edges,"mux_control_candidate",0)=={key(ctrl,(),left,target,(i,),b) for b in range(5)}
            assert [b["path"] for b in r["branches"]]==[
                [{"decision_id":0,"arm":"true"}],[{"decision_id":0,"arm":"false"}]]
    assert seen==want,{"missing":sorted(want-seen),"extra":sorted(seen-want)}
    assert delta["new_unique_supported_assignments"]==63
    return {"status":"passed","assignments":63,"bitwise_candidates":62,
            "mux_data_candidates":310,"mux_control_candidates":155,"constant_positions":1}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"selector_recovery.result.json"
    summary=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items() if k!="recovered"}
                             for c in report["cases"]]},indent=2),encoding="utf-8")
    save()
    try:
        fixture,_=extract(run/"fixture",TOP,[FIXTURE])
        report["fixture"]=check_fixture(fixture)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.selector_recovery_pr75",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,baselines,linked,owner in [
            ("alu","cv32e40p_alu",d.parent/"alu",
             ((479,254,225,477),(130,61,69,21),(43,8,35,74),(66,28,38,1421),(63,0,63,0)),64,
             "cv32e40p_alu.ff_one_i"),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             ((1199,531,668,2842),(378,245,133,2469),(66,24,42,375),(165,39,126,2030),(70,1,69,128)),215,
             "cv32e40p_core.ex_stage_i.alu_i.ff_one_i")]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_selector_recovery=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx)
            for channel,expected in zip(CHANNELS,baselines):
                c=old[channel]["counts"]
                field="assignments" if channel==CHANNELS[0] else "captured"
                assert tuple(c[x] for x in (field,"supported","partial","edges"))==expected,(channel,c)
            delta=compare(old,new,{i["path"]:i["module"] for i in idx["instances"]})
            assert delta["previous_linked_support"]==linked
            case={"name":name,**delta,"truncated_analyzers":new["analysis_limits"]["truncated_analyzers"]}
            report["cases"].append(case)
            save()
            case["tree_oracle"]=check_tree(delta,owner)
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
