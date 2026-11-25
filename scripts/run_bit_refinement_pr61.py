"""Exact source-derived divider and FF-one LUT oracles plus specialization fixture."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

from scripts.run_array_pr60 import extract
from scripts.run_priority_pr47 import simulate
from scripts.run_scalability_pr55 import ALU_FILES
from scripts.rtl_fixtures import load_lock, verify_checkout
from rtlprep.annotated_evaluation import load_annotations, evaluate_case

ROOT=Path(__file__).resolve().parents[1]
TOP="bit_refinement_pr61"
FIXTURE=ROOT/"tests/fixtures/bit_refinement_pr61.sv"

def check_reverse(graph,base,source,target,width):
    rows=[e for e in graph["bit_dependency_graph"]["edges"] if e["target"]==base+"."+target]
    actual={(e["source"],e["source_bit"],e["target_bit"]) for e in rows}
    expected={(base+"."+source,width-1-i,i) for i in range(width)}
    assert actual==expected and len(rows)==width,{"missing":sorted(expected-actual),"unexpected":sorted(actual-expected),"rows":len(rows)}
    return len(rows)

def check_lut(graph,target,width,depth):
    rows=[r for r in graph["array_dependencies"]["items"] if r.get("target")==target]
    coords=[c for r in rows for c in r.get("constant_target_coordinates",[])]
    actual={(tuple(c["target_packed_indices"]),c["target_bit"],c["value"]) for c in coords}
    expected={((i,),b,(i>>b)&1) for i in range(depth) for b in range(width)}
    assert actual==expected and len(coords)==len(expected),{
        "target":target,"missing":sorted(expected-actual),"unexpected":sorted(actual-expected),
        "rows":rows}
    assert all(c["target"]==target and c["target_unpacked_indices"]==[] for c in coords)
    assert len(rows)==depth and all(r["coverage"]=="array_position_candidates" and r["edge_count"]==0 for r in rows),rows
    return len(coords)

def execute(out):
    out=out.resolve()
    entries=load_lock()
    for entry in entries:
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    entry=next(e for e in entries if e["repository"]=="openhwfoundation/cv32e40p")
    upstream=ROOT/entry["destination"]
    verify_checkout(upstream,entry)
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    fixture_dir=run/"fixture"
    graph=extract(fixture_dir,TOP,[FIXTURE])
    fixture_edges=sum(check_reverse(graph,TOP+"."+inst,"a","rev",width)
                      for inst,width in (("u0",8),("u1",5)))
    fixture_constants=sum(check_lut(graph,TOP+"."+inst+".lut",3,width)
                          for inst,width in (("u0",8),("u1",5)))
    assert not graph["bit_dependency_graph"]["counts"]["truncated"]
    assert not graph["array_dependencies"]["counts"]["truncated"]
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.bit_refinement_pr61",fixture_dir/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0),counts
    alu=extract(run/"cv32e40p_alu","cv32e40p_alu",[upstream/p for p in ALU_FILES],[upstream/"rtl/include"])
    recovered=check_reverse(alu,"cv32e40p_alu.alu_div_i","ResReg_DP","ResReg_DP_rev",32)
    # The instance is discovered by its resolved target, not a guessed name.
    targets={r["target"] for r in alu["array_dependencies"]["items"]
             if isinstance(r.get("target"),str) and r["target"].endswith(".index_lut")}
    assert len(targets)==1,targets
    constant_count=check_lut(alu,next(iter(targets)),5,32)
    bit=alu["bit_dependency_graph"]
    arrays=alu["array_dependencies"]
    before={"assignments":479,"supported":222,"partial":257,"edges":445,"truncated":False}
    c=bit["counts"]
    assert c["assignments"]==before["assignments"] and c["supported"]>=254 and c["partial"]<=225 and c["edges"]>=477 and not c["truncated"],c
    assert not arrays["counts"]["truncated"]
    annotations=load_annotations(ROOT/"benchmarks/annotations/pr56.json")
    case=next(x for x in annotations["cases"] if x["name"]=="cv32e40p_alu")
    frozen=evaluate_case(case,alu)
    for channel,tp in (("signal",10),("bit",65)):
        row=frozen[channel]
        assert (row["tp"],row["fp"],row["fn"])==(tp,0,0),row
    verify_checkout(upstream,entry)
    report={"status":"passed","fixture":{"source_fingerprint":graph["source_fingerprint"],
              "reversal_edges":fixture_edges,"constant_coordinates":fixture_constants,"behavioral_vectors":256},
            "cv32e40p_alu":{"source_fingerprint":alu["source_fingerprint"],"commit":entry["commit"],
              "legacy_before_pr60":before,"legacy_after":c,"recovered_divider_positions":recovered,
              "new_legacy_supported":c["supported"]-before["supported"],
              "reviewed_lut_constant_coordinates":constant_count,"array_counts":arrays["counts"],
              "legacy_partial_reasons":dict(Counter(r.get("reason","unknown") for r in bit["items"] if r["coverage"]=="partial")),
              "array_partial_reasons":dict(Counter(r.get("reason","unknown") for r in arrays["items"] if r["coverage"]=="partial")),
              "frozen_pr56":{channel:{k:frozen[channel][k] for k in ("tp","fp","fn","precision","recall","f1")} for channel in ("signal","bit")}},
            "scope":"source_annotated_divider_lut_and_fixture_only","functional_influence":"not_proven",
            "formal_proof":"not_performed","design_coverage":"not_measured"}
    path=run/"bit_refinement.result.json"
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
