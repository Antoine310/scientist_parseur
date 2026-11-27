"""Independent direct dynamic conversion oracle, real slang and binary simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.dynamic_conversion_candidates import audit_dynamic_conversions
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="dynamic_conversions_pr116"
FIXTURE=ROOT/"tests/fixtures/dynamic_conversions_pr116.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(3,3,0,16,4),"alu":(0,0,0,0,0),
              "core":(94,1,93,16,16)}[name]
    assert tuple(c[k] for k in ("roots","supported","partial","potential_pairs","zero_fill_coordinates"))==expected,c
    assert c["supported_residual"]==0
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    good=[r for r in result["items"] if r["coverage"]!="partial"]
    if name=="fixture":
        wanted={"z":("u","zero_extend",list(range(4)),list(range(4,8))),
                "ext":("s","sign_extend",[0,1,2,3,3,3,3,3],[]),
                "trunc":("wide","truncate_msb",list(range(4)),[])}
    elif name=="core":
        wanted={"csr_rdata_int":("tinfo_types","zero_extend",list(range(16)),list(range(16,32)))}
        assert (c["ast_occurrences"],c["historical_rows"])==(3811,1199)
        assert c["supported_without_flat_id"]==1
        assert result["partial_reasons"]=={"unsupported_integral_type":93}
        residual=[r for r in result["items"] if r["historical_residual"]]
        assert len(residual)==1 and residual[0]["flat_assignment_id"]==314
        assert good[0]["instance"]=="cv32e40p_core.cs_registers_i"
        assert good[0]["historical_status"]=="selection_gate_negative"
    else:
        wanted={}
        assert (c["ast_occurrences"],c["historical_rows"])==(612,479)
    seen=set()
    for row in good:
        x=row["candidate"]
        target=x["target"]["signal"].rsplit(".",1)[1]
        assert target in wanted and target not in seen
        seen.add(target)
        src,mode,bits,zero=wanted[target]
        assert x["source"]["signal"]==row["instance"]+"."+src
        assert x["target"]["signal"]==row["instance"]+"."+target
        assert x["mode"]==mode
        assert x["pairs"]==[{"source_bit":s,"target_bit":i} for i,s in enumerate(bits)]
        assert x["zero_fill_bits"]==zero
    assert seen==set(wanted)


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
        result=audit_dynamic_conversions(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".dynamic-conversions.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.dynamic_conversions_pr116",run/"simulation")
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
