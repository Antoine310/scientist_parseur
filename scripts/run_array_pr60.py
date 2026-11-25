"""Real slang array-coordinate oracle, behavioral fixture and pinned ALU diagnostic."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.run_priority_pr47 import simulate
from scripts.run_scalability_pr55 import write_manifest, ALU_FILES
from scripts.rtl_fixtures import load_lock, verify_checkout

ROOT=Path(__file__).resolve().parents[1]
TOP="array_pr60"
FIXTURE=ROOT/"tests/fixtures/array_pr60.sv"

def edge_key(e):
    return (e["source"],tuple(e["source_unpacked_indices"]),tuple(e["source_packed_indices"]),
            e["source_bit"],e["target"],tuple(e["target_unpacked_indices"]),
            tuple(e["target_packed_indices"]),e["target_bit"])

def expected_edges():
    expected=set()
    def add(source,target,source_bits,target_bits,su=(),sp=(),tu=(),tp=()):
        expected.update((TOP+"."+source,su,sp,sb,TOP+"."+target,tu,tp,tb)
                        for sb,tb in zip(source_bits,target_bits))
    bits=range(8)
    add("a","arr",bits,bits,tu=(1,))
    add("b","arr",bits,bits,tu=(2,))
    add("arr","word_o",bits,bits,su=(1,))
    add("arr","slice_o",range(2,6),range(4),su=(2,))
    add("arr","bit_o",[7],[0],su=(1,))
    add("b","packed_arr",bits,bits,tp=(0,))
    add("a","packed_arr",bits,bits,tp=(1,))
    add("packed_arr","packed_o",range(4),range(4),sp=(0,))
    add("a","grid",bits,bits,tu=(2,0))
    add("grid","grid_o",bits,bits,su=(2,0))
    return expected

def extract(directory,top,sources,includes=()):
    directory.mkdir()
    manifest=directory/"design.json"
    write_manifest(manifest,top,sources,includes)
    result=dependency_design(load_design(manifest),directory,180)
    assert result["status"]=="passed",result
    graph=json.loads((directory/"rtl_dependencies.json").read_text())
    (directory/"array.diagnostic.json").write_text(json.dumps(graph["array_dependencies"],indent=2))
    return graph

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
    data=graph["array_dependencies"]
    expected=expected_edges()
    actual={edge_key(e) for e in data["edges"]}
    assert len(expected)==65
    assert data["counts"]=={"captured":11,"supported":10,"partial":1,"edges":65,"truncated":False},data
    assert actual==expected and len(data["edges"])==len(actual),{
        "missing":sorted(expected-actual),"unexpected":sorted(actual-expected)}
    partial=[r for r in data["items"] if r["coverage"]=="partial"]
    assert len(partial)==1,partial
    row=partial[0]
    assert row["source"]==TOP+".arr" and row["target"]==TOP+".dynamic_o",row
    assert row["reason"]=="dynamic_or_unproven_index" and row["edge_count"]==0,row
    assert row["source_selector_references"]==[TOP+".idx"],row
    counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.array_pr60",fixture_dir/"simulation")
    assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0),counts
    alu=extract(run/"cv32e40p_alu","cv32e40p_alu",[upstream/p for p in ALU_FILES],[upstream/"rtl/include"])
    legacy=alu["bit_dependency_graph"]
    arrays=alu["array_dependencies"]
    # Keep the frozen historical benchmark comparable. The new coordinate
    # edges have a different schema and must not be added to flat edges.
    # Historical floor, not a ceiling: later refinements may recover positions.
    c=legacy["counts"]
    assert c["assignments"]==479 and c["supported"]>=222 and c["partial"]<=257, c
    assert c["edges"]>=445 and not c["truncated"],c
    verify_checkout(upstream,entry)
    report={"status":"passed","fixture":{"source_fingerprint":graph["source_fingerprint"],
                "counts":data["counts"],"reviewed_coordinate_edges":len(expected),
                "matched_coordinate_edges":len(actual),"dynamic_rejections":1,"behavioral_vectors":512},
            "cv32e40p_alu":{"source_fingerprint":alu["source_fingerprint"],"commit":entry["commit"],
                "legacy_bit_graph_counts":legacy["counts"],
                "legacy_partial_reasons":dict(Counter(r.get("reason","unknown") for r in legacy["items"]
                                                      if r["coverage"]=="partial")),
                "array_counts":arrays["counts"],
                "array_partial_reasons":dict(Counter(r.get("reason","unknown") for r in arrays["items"]
                                                      if r["coverage"]=="partial")),
                "array_oracle":"not_performed"},
            "functional_influence":"not_proven","formal_proof":"not_performed","design_coverage":"not_measured"}
    path=run/"array.result.json"
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
