"""Independent direct enum conversion oracle, real slang and binary simulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.enum_conversion_candidates import audit_enum_conversions
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="enum_conversions_pr117"
FIXTURE=ROOT/"tests/fixtures/enum_conversions_pr117.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(5,5,0,2,14,1,4),"alu":(0,0,0,0,0,0,0),
              "core":(93,93,0,2,318,1,92)}[name]
    assert tuple(c[k] for k in ("roots","supported","partial","potential_pairs","value_records",
                                 "supported_residual","supported_without_flat_id"))==expected,c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    assert c["stored_coordinates"]==c["potential_pairs"]+c["value_records"]
    observed=Counter(); cast=[]
    if name=="fixture":
        values={"op":{"OP_A":0,"OP_B":1},"fmt":{"FMT_A":2,"FMT_B":5}}
        wanted=Counter((t,v) for t,m in values.items() for v in m)
    elif name=="core":
        values={"fpu_op":dict(zip("FMADD FNMSUB ADD MUL DIV SQRT SGNJ MINMAX CMP CLASSIFY F2F F2I I2F CPKAB CPKCD".split(),range(15))),
                "fpu_int_fmt_o":{"INT8":0,"INT16":1,"INT32":2},
                "fpu_src_fmt_o":{"FP32":0,"FP64":1,"FP16":2,"FP8":3,"FP16ALT":4},
                "fpu_dst_fmt_o":{"FP32":0,"FP64":1,"FP16":2,"FP8":3,"FP16ALT":4}}
        wanted=Counter({("fpu_op",v):n for v,n in zip(values["fpu_op"],[5,2,4,3,2,2,7,3,7,2,2,2,2,1,1])})
        wanted.update({("fpu_int_fmt_o",v):1 for v in values["fpu_int_fmt_o"]})
        wanted.update({("fpu_src_fmt_o",v):n for v,n in zip(values["fpu_src_fmt_o"],[4,3,3,3,9])})
        wanted.update({("fpu_dst_fmt_o",v):n for v,n in zip(values["fpu_dst_fmt_o"],[5,2,3,3,9])})
        assert (c["ast_occurrences"],c["historical_rows"])==(3811,1199)
    else:
        values={}; wanted=Counter()
        assert (c["ast_occurrences"],c["historical_rows"])==(612,479)
    for row in result["items"]:
        x=row["candidate"]; t=x["target"]["signal"].rsplit(".",1)[1]
        assert x["target"]["signal"]==row["instance"]+"."+t
        if x["family"]=="enum_binary_cast":
            cast.append(row)
            assert x["enum_domain_size"]==4
            assert x["pairs"]==[{"source_bit":s,"target_bit":i} for i,s in enumerate([3,4] if name=="fixture" else [13,14])]
            assert x["source"]["signal"]==row["instance"]+("."+"word" if name=="fixture" else ".csr_wdata_int")
            assert t==("state" if name=="fixture" else "mstatus_fs_n")
            if name=="core":
                assert row["flat_assignment_id"]==314 and row["instance"]=="cv32e40p_core.cs_registers_i"
        else:
            v=x["enum_value"]; expected_value=values[t][v]
            observed[(t,v)]+=1
            assert row["flat_assignment_id"] is None and x["potential_pairs"]==0
            assert x["value"]==expected_value
            n=len(x["target"]["bits_lsb_first"])
            assert x["target"]["bits_lsb_first"]==list(range(n))
            assert x["values_lsb_first"]==[(expected_value>>i)&1 for i in range(n)]
            assert x["permanent_constant"]=="not_inferred"
            if name=="core":
                assert row["instance"]=="cv32e40p_core.id_stage_i.decoder_i"
                assert row["historical_status"]=="selection_gate_negative"
                assert x["encoding_method"]==("explicit_unsigned_initializer" if "fmt" in t and "int" not in t else "implicit_declaration_order")
    assert observed==wanted and len(cast)==(0 if name=="alu" else 1)


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
        result=audit_enum_conversions(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".enum-conversions.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.enum_conversions_pr117",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":256,"word_checks_per_vector":3,
            "total_checks":768,"source_sha256":file_sha(FIXTURE)}
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
