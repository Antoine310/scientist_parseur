"""PR71: fixed packed coordinate evidence, distinct from flat bit positions."""
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
TOP="packed_coordinates_pr71"
FIXTURE=ROOT/"tests/fixtures/packed_coordinates_pr71.sv"

def indexed_edges(data):
    by=defaultdict(list)
    for e in data["edges"]:
        i=e["assignment_id"]
        if type(i) is not int or not 0<=i<len(data["items"]):
            raise ValueError("coordinate assignment ID out of bounds")
        by[i].append(e)
    for i,r in enumerate(data["items"]):
        if r["edge_count"]!=len(by[i]):
            raise ValueError("coordinate edge count mismatch")
    return by

def compare(old,new,instances):
    excluded={"array_dependencies","analysis_limits"}
    if {k:v for k,v in old.items() if k not in excluded}!={k:v for k,v in new.items() if k not in excluded}:
        raise ValueError("non-coordinate graph changed")
    a,b=old["array_dependencies"],new["array_dependencies"]
    if b["counts"]["truncated"] or len(b["items"])<len(a["items"]):
        raise ValueError("coordinate budget hit or original inventory lost")
    before,after=indexed_edges(a),indexed_edges(b)
    for i,r in enumerate(a["items"]):
        if r["coverage"]!="partial" and (r!=b["items"][i] or before[i]!=after[i]):
            raise ValueError("old supported coordinate assignment changed")
    flat=new["bit_dependency_graph"]["items"]
    extensions=[]
    seen=set()
    for i,r in enumerate(b["items"]):
        if r.get("coordinate_evidence")!="pr71_fixed_packed":
            continue
        ordinal=r["flat_assignment_id"]
        if type(ordinal) is not int or not 0<=ordinal<len(flat) or ordinal in seen:
            raise ValueError("invalid or repeated flat assignment link")
        seen.add(ordinal)
        f=flat[ordinal]
        loc=r.get("source_location") or {}
        floc=f.get("source_location") or {}
        if r["target"]!=f["target"] or any(loc.get(k)!=floc.get(k) for k in ("file","line")):
            raise ValueError("coordinate/flat identity mismatch")
        fixed=r.get("constant_target_positions",[])
        coords=[(tuple(e["target_packed_indices"]),e["target_bit"]) for e in [*after[i],*fixed]]
        if len(coords)!=len(set(coords)) or any(e["target"]!=f["target"] for e in [*after[i],*fixed]):
            raise ValueError("duplicate or inconsistent target coordinates")
        if r["coverage"]=="partial" and coords:
            raise ValueError("partial coordinate row emitted positions")
        if r["coverage"]!="partial" and not coords:
            raise ValueError("empty supported coordinate row")
        extensions.append({"coordinate_assignment_id":i,"flat_assignment_id":ordinal,
            "instance":owner_for(r["target"],instances),"target":r["target"],
            "source_location":r.get("source_location"),"coverage":r["coverage"],
            "reason":r.get("reason"),"flat_coverage":f["coverage"],
            "flat_reason":f.get("reason"),"edges":after[i],"constant_positions":fixed})
    supported=[r for r in extensions if r["coverage"]!="partial"]
    additional=[r for r in supported if r["flat_coverage"]=="partial"]
    return {"before":a["counts"],"after":b["counts"],
            "flat_counts_unchanged":new["bit_dependency_graph"]["counts"],
            "extension_rows":extensions,"extension_supported":len(supported),
            "extension_partial":len(extensions)-len(supported),
            "flat_partial_with_new_coordinate_evidence":len(additional),
            "new_supported_by_instance":dict(Counter(r["instance"] for r in additional)),
            "new_dynamic_edges":sum(len(r["edges"]) for r in additional),
            "new_constant_positions":sum(len(r["constant_positions"]) for r in additional),
            "remaining_extension_reasons":dict(Counter(r["reason"] for r in extensions if r["coverage"]=="partial"))}

def check_fixture(graph):
    data=graph["array_dependencies"]
    assert data["counts"]=={"captured":4,"supported":4,"partial":0,"edges":8,"truncated":False},data["counts"]
    expected={(s,b,d,b) for s,d in ((1,2),(2,1)) for b in range(4,8)}
    actual={(e["source_packed_indices"][0],e["source_bit"],e["target_packed_indices"][0],e["target_bit"])
            for e in data["edges"] if e["source"]==TOP+".p" and e["target"]==TOP+".q"}
    fixed=[c for r in data["items"] for c in r.get("constant_target_positions",[])]
    assert actual==expected and len(actual)==8
    assert {(tuple(c["target_packed_indices"]),c["target_bit"]) for c in fixed}=={
        ((i,),b) for i in (1,2) for b in range(4,8)} and len(fixed)==8
    assert all(r["procedure_kind"]=="AlwaysFF" and r["nonblocking"] for r in data["items"])
    return {"reviewed_edges":8,"constant_positions":8,"behavioral_vectors":256,
            "reset_checks":1,"word_swap_checks":256}

def check_register_file(delta):
    """Independent source-derived oracle for default integer RF write sites."""
    target="cv32e40p_core.id_stage_i.register_file_i.mem"
    rows=[r for r in delta["extension_rows"] if r["target"]==target]
    expected={119:[0],122:[0],131:list(range(1,32)),133:list(range(1,32)),134:list(range(1,32))}
    observed=defaultdict(list)
    for r in rows:
        line=(r["source_location"] or {}).get("line")
        if line not in expected:
            continue
        assert r["coverage"]!="partial",r
        assert r["flat_coverage"]=="partial",r
        positions=r["constant_positions"] if line in (119,122,131) else r["edges"]
        assert len(positions)==32,r
        indices={tuple(e["target_packed_indices"]) for e in positions}
        assert len(indices)==1 and {e["target_bit"] for e in positions}==set(range(32)),r
        idx=next(iter(indices))
        assert len(idx)==1
        if line in (133,134):
            src="wdata_b_i" if line==133 else "wdata_a_i"
            assert all(e["source"]==target.rsplit(".",1)[0]+"."+src
                       and e["source_packed_indices"]==[] and e["source_bit"]==e["target_bit"]
                       for e in positions),r
            assert not r["constant_positions"]
        else:
            assert not r["edges"]
        observed[line].append(idx[0])
    observed={k:sorted(v) for k,v in observed.items()}
    assert observed==expected,observed
    return {"status":"passed","assignment_rows":95,"dynamic_edges":1984,
            "constant_positions":1056,"observed_word_indices_by_line":observed}

def execute(out):
    out=out.resolve()
    for entry in load_lock():
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"packed_coordinates.result.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        fixture,_=extract(run/"fixture",TOP,[FIXTURE])
        report["fixture"]=check_fixture(fixture)
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.packed_coordinates_pr71",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture"]["simulation"]="passed"
        save()
        d=diagnostics(run/"reference")
        ref=json.loads(d.read_text())
        for name,top,folder,baseline,arrays in [
            ("alu","cv32e40p_alu",d.parent/"alu",(479,254,225,477),(94,33,61)),
            ("core","cv32e40p_core",Path(ref["core_reference_report"]).parent/"static",
             (1199,531,668,2842),(221,94,127))]:
            ast=read_ast(folder/"elaborated_ast.json")
            idx=json.loads((folder/"rtl_index.json").read_text())
            old=build_dependency_graph(ast,expected_top=top,index=idx,enable_packed_coordinates=False,enable_mux=False,enable_bitwise=False)
            new=build_dependency_graph(ast,expected_top=top,index=idx,enable_mux=False,enable_bitwise=False)
            c=old["bit_dependency_graph"]["counts"]
            assert tuple(c[k] for k in ("assignments","supported","partial","edges"))==baseline,c
            c=old["array_dependencies"]["counts"]
            assert tuple(c[k] for k in ("captured","supported","partial"))==arrays,c
            delta=compare(old,new,{i["path"]:i["module"] for i in idx["instances"]})
            case={"name":name,**delta,"truncated_analyzers":new["analysis_limits"]["truncated_analyzers"]}
            if name=="core":
                case["register_file_oracle"]=check_register_file(delta)
            report["cases"].append(case)
            save()
            print(json.dumps({k:v for k,v in case.items() if k!="extension_rows"},indent=2),flush=True)
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
