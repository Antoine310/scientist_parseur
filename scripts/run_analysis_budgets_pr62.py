"""Real slang budget-boundary probes and pinned ALU partial-reason inventory."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import tempfile

from rtlprep.analysis_budgets import ANALYZERS, DEFAULT_BUDGET, AnalysisBudgetError, read_ast
from rtlprep.dependencies import build_dependency_graph
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.run_scalability_pr55 import TOP, ALU_FILES, generate_pipeline, write_manifest, oracle
from scripts.rtl_fixtures import load_lock, verify_checkout

ROOT=Path(__file__).resolve().parents[1]

def validate_analyzer_inventory(limits):
    """Fresh extractions must report every registered analyzer by name."""
    actual=set(limits["analyzers"])
    expected=set(ANALYZERS)
    assert actual==expected, {"missing":sorted(expected-actual),
                              "unexpected":sorted(actual-expected)}

def extract(directory,top,sources,includes=()):
    directory.mkdir(exist_ok=True)
    manifest=directory/"design.json"
    write_manifest(manifest,top,sources,includes)
    result=dependency_design(load_design(manifest),directory,180)
    assert result["status"]=="passed",result
    graph=json.loads((directory/"rtl_dependencies.json").read_text())
    index=json.loads((directory/"rtl_index.json").read_text())
    limits=graph["analysis_limits"]
    assert result["analysis_limits"]["assessment"]==limits["assessment"]
    assert result["analysis_limits"]["truncated_analyzers"]==limits["truncated_analyzers"]
    validate_analyzer_inventory(limits)
    return graph,index

def gate_probe(ast,top,index,budget,stage):
    try:
        build_dependency_graph(ast,expected_top=top,index=index,budget=budget)
    except AnalysisBudgetError as exc:
        assert exc.details["stage"]==stage,exc.details
        return exc.details
    raise AssertionError("expected gate rejection: "+stage)

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
    cases=[]
    gates=[]
    for n in (8,512,520):
        directory=run/f"stages-{n}"
        directory.mkdir()
        source=directory/"pipeline.sv"
        source.write_text(generate_pipeline(n),encoding="utf-8")
        graph,index=extract(directory,TOP,[source])
        limits=graph["analysis_limits"]
        reports=limits["analyzers"]
        expected=n>512
        assert reports["register_flow"]["truncated"] is expected
        assert reports["sequential_candidates"]["upstream_truncation"]==("register_flow" if expected else None)
        assert reports["intercycle_dependencies"]["upstream_truncation"]==("sequential_candidates" if expected else None)
        if expected:
            assert limits["assessment"]=="reported_truncation"
            assert set(("register_flow","sequential_candidates","intercycle_dependencies"))<=set(limits["truncated_analyzers"])
        checks=oracle(index,graph,n)
        if n==8:
            ast=read_ast(directory/"elaborated_ast.json")
            gates.append(gate_probe(ast,TOP,index,replace(DEFAULT_BUDGET,max_ast_values=1),"ast_admission"))
            gates.append(gate_probe(ast,TOP,index,replace(DEFAULT_BUDGET,max_graph_values=1),"graph_publication"))
        cases.append({"stages":n,"oracle":checks,"source_fingerprint":graph["source_fingerprint"],
                      "ast_metrics":limits["ast_metrics"],"graph_metrics":limits["graph_metrics_excluding_this_report"],
                      "assessment":limits["assessment"],"truncated_analyzers":limits["truncated_analyzers"],
                      "register_flow":reports["register_flow"],"sequential_candidates":reports["sequential_candidates"],
                      "intercycle_dependencies":reports["intercycle_dependencies"]})
    alu,_=extract(run/"cv32e40p_alu","cv32e40p_alu",[upstream/p for p in ALU_FILES],[upstream/"rtl/include"])
    legacy=alu["bit_dependency_graph"]["counts"]
    assert legacy=={"assignments":479,"supported":254,"partial":225,"edges":477,"truncated":False},legacy
    limits=alu["analysis_limits"]
    bit=limits["analyzers"]["bit_accesses"]
    assert sum(bit["partial_reasons"].values())==bit["status_counts"].get("partial",0)
    assert limits["analyzers"]["bit_dependency_graph"]["partial_reasons"]=={
        "partial_bit_access":223,"unproven_packed_layout":1,"target_rhs_width_mismatch":1}
    verify_checkout(upstream,entry)
    report={"status":"passed","global_gate_probes":gates,"pipeline_cases":cases,
            "cv32e40p_alu":{"commit":entry["commit"],"source_fingerprint":alu["source_fingerprint"],
                "legacy_bit_graph_counts":legacy,"analysis_limits":limits},
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed"}
    path=run/"analysis_budgets.result.json"
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Report: {path}")
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
