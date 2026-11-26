"""PR74 — exact candidate-coordinate oracles and compact same-AST comparison."""
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
TOP="dynamic_pr74"
FIXTURE=ROOT/"tests/fixtures/dynamic_pr74.sv"
CHANNELS=("bit_dependency_graph","array_dependencies","bitwise_dependencies","mux_dependencies")

def coord(e,prefix):
    return (e[prefix],tuple(e[prefix+"_unpacked_indices"]),
            tuple(e[prefix+"_packed_indices"]),e[prefix+"_bit"])

def validate_row(row,edges):
    domain=row["selector"]
    alternatives=row["alternatives"]
    assert domain["role"] in ("read","write")
    lo,hi=sorted(domain["declared_bounds"])
    maximum=(1<<domain["selector_width"])-1
    assert domain["indices"]==list(range(lo,min(hi,maximum)+1))
    assert domain["indices"] and domain["numeric_out_of_range_possible"]==(lo>0 or maximum>hi)
    assert [a["alternative_id"] for a in alternatives]==list(range(len(alternatives)))
    assert [a["selector_value"] for a in alternatives]==domain["indices"]
    ctrl={coord(s,"source") for s in domain["selector_sources"]}
    assert ctrl and len(ctrl)==len(domain["selector_sources"])
    seen=set()
    target_sets=[]
    for e in edges:
        assert e["relation"] in ("index_data_candidate","index_control_candidate")
        aid=e["alternative_id"]
        assert type(aid) is int and 0<=aid<len(alternatives)
        key=(aid,e["relation"],coord(e,"source"),coord(e,"target"))
        assert key not in seen
        seen.add(key)
    def selected_index(c):
        kind=domain["dimension_kind"]
        ordinal=domain["dimension_ordinal"]
        if kind=="bit":
            assert ordinal==len(c[2])
            return c[3]
        assert kind in ("unpacked","packed")
        return c[1 if kind=="unpacked" else 2][ordinal]
    for a in alternatives:
        aid=a["alternative_id"]
        value=a["selector_value"]
        data=[e for e in edges if e["alternative_id"]==aid and e["relation"]=="index_data_candidate"]
        control=[e for e in edges if e["alternative_id"]==aid and e["relation"]=="index_control_candidate"]
        fixed=[coord(e,"target") for e in a["constant_target_positions"]]
        targets={coord(e,"target") for e in data}|set(fixed)
        assert targets and all(c[0]==row["target"] for c in targets)
        assert len(fixed)==len(set(fixed))
        assert len(data)+len(fixed)==len(targets)
        assert {(coord(e,"source"),coord(e,"target")) for e in control}=={
            (s,t) for s in ctrl for t in targets}
        if domain["role"]=="write":
            assert all(selected_index(t)==value for t in targets)
        else:
            assert data and not fixed and all(selected_index(coord(e,"source"))==value for e in data)
        target_sets.append(targets)
    if domain["role"]=="read":
        assert all(s==target_sets[0] for s in target_sets)
    else:
        assert len(set().union(*target_sets))==sum(map(len,target_sets))

def check_fixture(graph):
    d=graph["dynamic_dependencies"]
    assert d["counts"]=={"captured":5,"supported":5,"partial":0,"edges":188,"truncated":False},d["counts"]
    expected={
        "read_bit":("read","bit","p",1),
        "read_word":("read","packed","p",4),
        "read_unpacked":("read","unpacked","u",4),
        "write_word":("write","packed","d",4),
        "write_constant":("write","packed",None,4),
    }
    for target,(role,kind,src,n) in expected.items():
        target=TOP+"."+target
        matches=[(i,r) for i,r in enumerate(d["items"]) if r["target"]==target]
        assert len(matches)==1,matches
        i,r=matches[0]
        local=[e for e in d["edges"] if e["assignment_id"]==i]
        validate_row(r,local)
        assert r["selector"]["role"]==role and r["selector"]["dimension_kind"]==kind
        assert r["selector"]["indices"]==list(range(4))
        assert {coord(s,"source") for s in r["selector"]["selector_sources"]}=={
            (TOP+".idx",(),(),j) for j in range(2)}
        for a in r["alternatives"]:
            j=a["selector_value"]
            dest={(target,(),(j,) if role=="write" else (),b) for b in range(n)}
            data=[e for e in local if e["alternative_id"]==j and e["relation"]=="index_data_candidate"]
            if src is None:
                assert not data and {coord(p,"target") for p in a["constant_target_positions"]}==dest
            else:
                assert not a["constant_target_positions"]
                def source(b):
                    if kind=="bit":
                        return (TOP+".p",(),(0,),j)
                    if role=="write":
                        return (TOP+".d",(),(),b)
                    if kind=="packed":
                        return (TOP+".p",(),(j,),b)
                    return (TOP+".u",(j,),(),b)
                assert {(coord(e,"source"),coord(e,"target")) for e in data}=={
                    (source(b),(target,(),(j,) if role=="write" else (),b)) for b in range(n)}
    return {"assignments":5,"alternatives":20,"data_candidates":52,"control_candidates":136,
            "alternative_constant_positions":16,"behavioral_vectors":1024,"behavioral_checks":5120}

def compare(old,new,instances):
    excluded={"dynamic_dependencies","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={
        k:v for k,v in new.items() if k not in excluded},"non-dynamic graph changed"
    assert not old["dynamic_dependencies"]["items"]
    flat=new["bit_dependency_graph"]["items"]
    previous={r["flat_assignment_id"] for k in CHANNELS[1:] for r in new[k]["items"]
              if "flat_assignment_id" in r and r["coverage"]!="partial"
              and flat[r["flat_assignment_id"]]["coverage"]=="partial"}
    data=new["dynamic_dependencies"]
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
            assert not local and "selector" not in r and "alternatives" not in r
            reasons[r["reason"]]+=1
            continue
        validate_row(r,local)
        recovered.append({"flat_assignment_id":ordinal,"target":r["target"],
            "instance":owner_for(r["target"],instances),"source_location":r["source_location"],
            "already_supported":ordinal in previous,"selector":r["selector"],
            "alternatives":r["alternatives"],"edges":local})
    extra=[r for r in recovered if not r["already_supported"]]
    total=new["bit_dependency_graph"]["counts"]["assignments"]
    combined=new["bit_dependency_graph"]["counts"]["supported"]+len(previous)+len(extra)
    assert combined<=total and len(recovered)==data["counts"]["supported"] and not data["counts"]["truncated"]
    return {"flat_counts":new[CHANNELS[0]]["counts"],"array_counts":new[CHANNELS[1]]["counts"],
            "bitwise_counts":new[CHANNELS[2]]["counts"],"mux_counts":new[CHANNELS[3]]["counts"],
            "dynamic_counts":data["counts"],"previous_linked_support":len(previous),
            "new_unique_supported_assignments":len(extra),"overlap_with_previous":len(recovered)-len(extra),
            "minimum_combined_supported":combined,"remaining_without_linked_support":total-combined,
            "new_data_candidates":sum(e["relation"]=="index_data_candidate" for r in extra for e in r["edges"]),
            "new_control_candidates":sum(e["relation"]=="index_control_candidate" for r in extra for e in r["edges"]),
            "new_alternative_constant_positions":sum(len(a["constant_target_positions"]) for r in extra for a in r["alternatives"]),
            "new_by_instance":dict(Counter(r["instance"] for r in extra)),
            "remaining_dynamic_reasons":dict(reasons),"recovered":recovered}

def check_fifo_oracle(delta):
    owner="cv32e40p_core.if_stage_i.prefetch_buffer_i.fifo_i"
    target=owner+".mem_n"
    rows=[r for r in delta["recovered"] if r["target"]==target
          and (r["source_location"] or {}).get("line")==77]
    assert len(rows)==1,rows
    r=rows[0]
    assert r["selector"]["role"]=="write" and r["selector"]["indices"]==[0,1]
    assert {coord(s,"source") for s in r["selector"]["selector_sources"]}=={
        (owner+".write_pointer_q",(),(),0)}
    assert not r["already_supported"] and len(r["edges"])==128
    for j in (0,1):
        data=[e for e in r["edges"] if e["alternative_id"]==j and e["relation"]=="index_data_candidate"]
        control=[e for e in r["edges"] if e["alternative_id"]==j and e["relation"]=="index_control_candidate"]
        assert {(coord(e,"source"),coord(e,"target")) for e in data}=={
            ((owner+".data_i",(),(),b),(target,(),(j,),b)) for b in range(32)}
        assert {(coord(e,"source"),coord(e,"target")) for e in control}=={
            ((owner+".write_pointer_q",(),(),0),(target,(),(j,),b)) for b in range(32)}
        assert not r["alternatives"][j]["constant_target_positions"]
    return {"status":"passed","source_line":77,"indices":[0,1],"data_candidates":64,"control_candidates":64}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"dynamic.result.json"
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.dynamic_pr74",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,baselines,linked in [
            ("alu","cv32e40p_alu",d.parent/"alu",
             ((479,254,225,477),(130,61,69,21),(43,8,35,74),(66,28,38,1421)),64),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             ((1199,531,668,2842),(378,245,133,2469),(66,24,42,375),(165,39,126,2030)),214)]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_dynamic=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx)
            for channel,expected in zip(CHANNELS,baselines):
                c=old[channel]["counts"]
                k="assignments" if channel==CHANNELS[0] else "captured"
                assert tuple(c[x] for x in (k,"supported","partial","edges"))==expected,(channel,c)
            delta=compare(old,new,{i["path"]:i["module"] for i in idx["instances"]})
            assert delta["previous_linked_support"]==linked
            case={"name":name,**delta,"truncated_analyzers":new["analysis_limits"]["truncated_analyzers"]}
            report["cases"].append(case)
            save()
            if name=="core":
                case["fifo_oracle"]=check_fifo_oracle(delta)
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
