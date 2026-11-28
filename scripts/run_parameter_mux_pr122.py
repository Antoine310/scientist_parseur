"""Independent parameter mux oracle, real slang and binary simulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.parameter_mux_candidates import audit_parameter_mux
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="parameter_mux_pr122"
FIXTURE=ROOT/"tests/fixtures/parameter_mux_pr122.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(4,4,0,64,64,64,192),"alu":(0,0,0,0,0,0,0),
              "core":(6,6,0,0,192,192,384)}[name]
    assert tuple(c[k] for k in ("roots","supported","partial","potential_pairs","local_value_records",
                                "inactive_alternative_positions","stored_coordinates"))==expected,c
    assert len(result["items"])==c["roots"]
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"] and not result["partial_reasons"]
    seen=set(); ids=set()
    for row in result["items"]:
        i=row["flat_assignment_id"]; owner=row["instance"]; line=row["source"]["line"]
        assert type(i) is int and i not in ids and row["historical_status"]=="captured"
        ids.add(i)
        if name=="core":
            assert owner=="cv32e40p_core.cs_registers_i" and row["context"]=="AlwaysComb"
            assert i in range(10,16) and line==586+i-10 and row["historical_residual"]
            lane=(i-10)//3; src=("hwlp_start_i","hwlp_end_i","hwlp_cnt_i")[(i-10)%3]
            dest="csr_rdata_int"; v=0; child_param=parent_param="COREV_PULP"
            parent="cv32e40p_core"
            key=i
        else:
            assert name=="fixture" and owner in (TOP+".u_zero",TOP+".u_one") and row["context"]=="continuous"
            assert line in (7,8),(owner,line)
            lane=line-7; src="data_i"; dest=f"y{lane}"
            v=int(owner.endswith("u_one")); child_param="CFG"; parent_param=f"CFG{v}"; parent=TOP
            key=(owner,lane)
        assert key not in seen
        seen.add(key)
        x=row["candidate"]; dst=owner+"."+dest; source=owner+"."+src
        assert x["target"]==dst and x["alternative_source"]==source
        assert x["model"]=={"parameter_value":v,"lane":lane,"width":32,
                           "selected_branch":"packed_word" if v else "zero",
                           "domain":"defined_binary_inputs_only"}
        assert x["parameter_chain"]==[{"instance":owner,"parameter":child_param,"method":"immediate_parent_reference"},
                                      {"instance":parent,"parameter":parent_param,"method":"typed_literal_initializer"}]
        pairs=[{"source":source,"source_packed_indices":[lane],"source_bit":b,"target":dst,"target_bit":b}
               for b in range(32)]
        assert x["pairs"]==(pairs if v else []) and x["alternative_positions"]==([] if v else pairs)
        assert x["local_values"]==([] if v else [{"target":dst,"target_bit":b,"value":0} for b in range(32)])
        assert x["potential_pairs"]==32*v and x["permanent_constant"]=="not_inferred"
    if name=="core":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(3811,1199,6)
        assert seen==set(range(10,16))
    elif name=="alu":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(612,479,0)
        assert not seen
    else:
        # Use independent instance/line oracle rather than assuming a flat-ID order.
        assert seen=={(TOP+"."+u,lane) for u in ("u_zero","u_one") for lane in (0,1)}


def execute(out,reference=None):
    out=out.resolve()
    lock=load_lock()
    for e in lock:
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","rtl_equivalence":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,upstream=None):
        before={k:file_sha(folder/k) for k in INPUTS}
        ast=read_ast(folder/INPUTS[0])
        idx=json.loads((folder/INPUTS[1]).read_text())
        g=json.loads((folder/INPUTS[2]).read_text())
        start=perf_counter()
        result=audit_parameter_mux(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".parameter-mux.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"input_sha256":before,"detail_file":detail.name,
             "detail_sha256":file_sha(detail),"audit_seconds":elapsed,"upstream":upstream,
             "historical_unchanged":True,**{k:v for k,v in result.items() if k not in ("items",)}})
        save()
    try:
        extract_fixture(run/"fixture")
        case("fixture",run/"fixture")
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.parameter_mux_pr122",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":64,"word_checks_per_vector":4,
            "total_checks":256,"source_sha256":file_sha(FIXTURE)}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
        assert len(report["cases"])==3
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:3000])
        raise
    finally:
        save()
        print(path.read_text(),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--reference",type=Path)
    a=p.parse_args()
    execute(a.out,a.reference)
