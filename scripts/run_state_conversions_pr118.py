"""Independent state conversion oracle, real slang and binary simulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.state_conversion_candidates import audit_state_conversions
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="state_conversions_pr118"
FIXTURE=ROOT/"tests/fixtures/state_conversions_pr118.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(2,2,0,0,2,0,4,0,2),
              "alu":(81,81,0,81,0,160,0,0,31),
              "core":(1338,1296,42,1296,0,4022,0,31,1138)}[name]
    assert tuple(c[k] for k in ("roots","supported","partial","literal_sites","dynamic_sites",
                                 "expression_value_positions","potential_pairs","supported_residual",
                                 "supported_without_flat_id"))==expected,c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"]
    assert len(result["items"])==c["roots"]
    assert c["stored_coordinates"]==c["expression_value_positions"]+c["potential_pairs"]
    hist=Counter(); dynamic=set(); overlaps=set()
    for row in result["items"]:
        if row["coverage"]=="partial":
            continue
        x=row["candidate"]
        if row["historical_residual"]: overlaps.add(row["flat_assignment_id"])
        if x["family"]=="dynamic_statement":
            dst=x["target"]["signal"].rsplit(".",1)[1]; src=x["source"]["signal"].rsplit(".",1)[1]
            dynamic.add((src,dst))
            assert x["pairs"]==[{"source_bit":i,"target_bit":i} for i in range(2)]
            assert x["state_map"]==({"0":"0","1":"1","x":"0","z":"0"} if dst=="dst2" else {"0":"0","1":"1"})
        else:
            assert x["source_values_lsb_first"]==x["result_values_lsb_first"]
            assert x["coordinate_space"]=="expression_relative" and "target" not in x
            hist[(x["width"],int("".join(reversed(x["result_values_lsb_first"])),2))]+=1
    if name=="fixture":
        assert dynamic=={("src4","dst2"),("src2","dst4")} and not hist and not overlaps
    elif name=="alu":
        assert (c["ast_occurrences"],c["historical_rows"])==(612,479)
        assert not dynamic and not overlaps and not result["partial_reasons"]
        assert hist==Counter({(1,0):19,(1,1):16,(2,0):16,(2,1):5,(2,2):4,(2,3):5,(3,7):1,
            **{(4,v):1 for v in [0,1,4,7,8,10,11,12,13,14,15]},(4,3):3,(6,31):1})
    else:
        assert (c["ast_occurrences"],c["historical_rows"])==(3811,1199)
        assert not dynamic and overlaps==set(range(279,310))
        assert result["partial_reasons"]=={"state_width_or_signedness_changed":37,"unsupported_state_type":4,
                                           "unsupported_state_operand":1}
        wanted={(1,0):409,(1,1):621,(2,0):49,(2,1):21,(2,2):17,(2,3):12,
                (3,0):7,(3,1):4,(3,2):3,(3,3):3,(3,7):3,
                (4,0):3,(4,1):4,(4,2):1,(4,3):5,(4,4):2,(4,6):1,(4,7):2,(4,8):4,
                (4,10):1,(4,11):1,(4,12):3,(4,13):1,(4,14):2,(4,15):2,
                (5,0):3,(5,1):2,(5,16):3,(5,31):1,(6,0):5,(6,31):1,(32,0):74,(32,4):1}
        wanted.update({(5,v):1 for v in [2,4,5,6,8,9,10,12,13,14,15,*range(17,31)]})
        assert hist==Counter(wanted)


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
        result=audit_state_conversions(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".state-conversions.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.state_conversions_pr118",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":16,"word_checks_per_vector":2,
            "total_checks":32,"source_sha256":file_sha(FIXTURE)}
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
