"""PR76 — exact package layouts with same-AST comparison and independent oracles."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from rtlprep.typed_layout import REASONS
from scripts.cv32e40p_pr67 import owner_for
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock
from scripts.run_dynamic_pr74 import coord, validate_row

ROOT=Path(__file__).resolve().parents[1]
TOP="typed_layout_pr76"
FIXTURE=ROOT/"tests/fixtures/typed_layout_pr76.sv"
CHANNELS=("bit_dependency_graph","array_dependencies","bitwise_dependencies",
          "mux_dependencies","dynamic_dependencies","selector_recovery")

def validate(row,edges):
    proofs=row["type_proofs"]
    assert proofs and len({tuple(p["ast_path"]) for p in proofs})==len(proofs)
    assert any(p["kind"]=="package_type" for p in proofs)
    for p in proofs:
        if p["kind"]=="package_type":
            assert "::" in p["declared_type"] and " " not in p["declared_type"]
            assert p["canonical_type"].startswith(("logic","bit"))
        else:
            assert p["kind"]=="package_constant" and "::" in p["parameter"]
            assert type(p["index"]) is int and p["index"]>=0
    assert edges and all(e["target"]==row["target"] for e in edges)
    if row["mode"]=="dynamic":
        validate_row(row,edges)
    else:
        assert row["mode"]=="fixed"
        assert all(e["relation"]=="typed_fixed_position_candidate" for e in edges)
        assert len({coord(e,"target") for e in edges})==len(edges)

def check_dynamic(row,edges,source,target,selector,values,bits,role,offset=0,index_width=2):
    assert row["mode"]=="dynamic" and row["selector"]["role"]==role
    assert row["selector"]["indices"]==list(values)
    assert row["selector"]["dimension_kind"]=="packed"
    assert {coord(s,"source") for s in row["selector"]["selector_sources"]}=={
        (selector,(),(),j) for j in range(index_width)}
    for a in row["alternatives"]:
        value=a["selector_value"]
        aid=a["alternative_id"]
        assert not a["constant_target_positions"]
        local=[e for e in edges if e["alternative_id"]==aid]
        data={(coord(e,"source"),coord(e,"target")) for e in local if e["relation"]=="index_data_candidate"}
        control={(coord(e,"source"),coord(e,"target")) for e in local if e["relation"]=="index_control_candidate"}
        source_coord=lambda b:(source,(),(value,) if role=="read" else (),b+offset)
        target_coord=lambda b:(target,(),(value,) if role=="write" else (),b)
        assert data=={(source_coord(b),target_coord(b)) for b in range(bits)}
        assert control=={((selector,(),(),j),target_coord(b)) for j in range(index_width) for b in range(bits)}
        assert len(local)==bits*(1+index_width)

def check_fixture(graph):
    d=graph["typed_layout"]
    assert d["counts"]=={"captured":3,"supported":3,"partial":0,"edges":97,"truncated":False},d["counts"]
    seen=set()
    for i,row in enumerate(d["items"]):
        edges=[e for e in d["edges"] if e["assignment_id"]==i]
        validate(row,edges)
        t=row["target"]
        assert t not in seen
        seen.add(t)
        if t==TOP+".flag_o":
            assert row["mode"]=="fixed" and len(edges)==1
            assert coord(edges[0],"source")== (TOP+".state_i",(),(),1)
            assert coord(edges[0],"target")== (t,(),(),0)
            assert any(p.get("parameter")=="typed_layout_pkg::FLAG_INDEX" and p.get("index")==1 for p in row["type_proofs"])
        elif t==TOP+".read_o":
            check_dynamic(row,edges,TOP+".p",t,TOP+".addr_i",range(4),4,"read")
        else:
            assert t==TOP+".write_o"
            check_dynamic(row,edges,TOP+".d",t,TOP+".addr_i",range(4),4,"write")
    assert seen=={TOP+".flag_o",TOP+".read_o",TOP+".write_o"}
    return {"assignments":3,"fixed_candidates":1,"data_candidates":32,"control_candidates":64,
            "behavioral_vectors":1024,"behavioral_checks":3072}

def compare(old,new,instances):
    excluded={"typed_layout","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={
        k:v for k,v in new.items() if k not in excluded},"previous graph changed"
    assert not old["typed_layout"]["items"]
    flat=new[CHANNELS[0]]["items"]
    previous={r["flat_assignment_id"] for channel in CHANNELS[1:] for r in new[channel]["items"]
              if "flat_assignment_id" in r and r["coverage"]!="partial"
              and flat[r["flat_assignment_id"]]["coverage"]=="partial"}
    eligible={r["flat_assignment_id"] for r in new["dynamic_dependencies"]["items"]
              if r["coverage"]=="partial" and r.get("reason") in REASONS}
    data=new["typed_layout"]
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
            assert not edges and "type_proofs" not in r
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
    return {"previous_counts":{k:new[k]["counts"] for k in CHANNELS},
            "typed_layout_counts":data["counts"],"previous_linked_support":len(previous),
            "new_unique_supported_assignments":len(extra),"overlap_with_previous":len(recovered)-len(extra),
            "minimum_combined_supported":combined,"remaining_without_linked_support":total-combined,
            "new_candidates_by_relation":dict(Counter(e["relation"] for r in extra for e in r["edges"])),
            "new_by_instance":dict(Counter(r["instance"] for r in extra)),
            "new_by_mode":dict(Counter(r["mode"] for r in extra)),
            "remaining_reasons":dict(reasons),"recovered":recovered}

def check_core(delta):
    ctrl="cv32e40p_core.id_stage_i.controller_i"
    csr="cv32e40p_core.cs_registers_i"
    flags={1544:("debug_havereset_o","HAVERESET_INDEX",0),
           1545:("debug_running_o","RUNNING_INDEX",1),
           1546:("debug_halted_o","HALTED_INDEX",2)}
    accesses={549:("mhpmcounter_q","csr_rdata_int","read"),
              583:("mhpmevent_q","csr_rdata_int","read"),
              1405:("csr_wdata_int","mhpmevent_n","write")}
    seen=set()
    for r in delta["recovered"]:
        line=r["source_location"]["line"]
        assert line not in seen and not r["already_supported"]
        seen.add(line)
        edges=r["edges"]
        if line in flags:
            name,param,bit=flags[line]
            assert r["instance"]==ctrl and r["target"]==ctrl+"."+name
            assert r["mode"]=="fixed" and len(edges)==1
            assert coord(edges[0],"source")== (ctrl+".debug_fsm_cs",(),(),bit)
            assert coord(edges[0],"target")== (ctrl+"."+name,(),(),0)
            assert any(p.get("declared_type")=="cv32e40p_pkg::debug_state_e" and
                       p.get("canonical_type")=="logic[2:0]" for p in r["type_proofs"])
            assert any(p.get("parameter")=="cv32e40p_pkg::"+param and p.get("index")==bit for p in r["type_proofs"])
        else:
            assert line in accesses and r["instance"]==csr
            source,target,role=accesses[line]
            assert r["target"]==csr+"."+target
            assert any(p.get("declared_type")=="cv32e40p_pkg::csr_num_e" and
                       p.get("canonical_type")=="logic[11:0]" for p in r["type_proofs"])
            check_dynamic(r,edges,csr+"."+source,csr+"."+target,csr+".csr_addr_i",
                          range(32),32,role,index_width=5)
    assert seen==set(flags)|set(accesses),seen
    assert delta["new_unique_supported_assignments"]==6
    return {"status":"passed","debug_flags":3,"csr_accesses":3,"fixed_candidates":3,
            "data_candidates":3072,"control_candidates":15360}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"typed_layout.result.json"
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.typed_layout_pr76",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,baselines,linked in [
            ("alu","cv32e40p_alu",d.parent/"alu",
             ((479,254,225,477),(130,61,69,21),(43,8,35,74),(66,28,38,1421),(63,0,63,0),(63,63,0,527)),127),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             ((1199,531,668,2842),(378,245,133,2469),(66,24,42,375),(165,39,126,2030),(70,1,69,128),(63,63,0,527)),278)]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_typed_layout=False)
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
            if name=="core":
                case["type_oracle"]=check_core(delta)
            else:
                assert delta["typed_layout_counts"]["captured"]==0
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
