"""Independent CSR composition oracle, real slang and binary simulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.csr_composition_candidates import audit_csr_composition
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="csr_composition_pr120"
FIXTURE=ROOT/"tests/fixtures/csr_composition_pr120.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(64,64,0,864),"alu":(0,0,0,0),"core":(64,64,0,864)}[name]
    assert tuple(c[k] for k in ("roots","supported","partial","potential_pairs"))==expected,c
    assert len(result["items"])==c["roots"]
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0 and not c["truncated"] and not result["partial_reasons"]
    seen=set(); ids=set()
    for row in result["items"]:
        x=row["candidate"]; port=x["target"].rsplit(".",1)[1]; k=x["target_bit"]
        assert port in ("mhpmcounter_write_lower","mhpmcounter_write_upper") and 0<=k<32
        upper=port.endswith("upper"); base=2944 if upper else 2816
        assert (port,k) not in seen
        seen.add((port,k)); ids.add(row["flat_assignment_id"])
        assert row["context"]=="continuous" and row["historical_status"]=="captured"
        owner=row["instance"]
        if name=="core":
            assert owner=="cv32e40p_core.cs_registers_i" and row["historical_residual"]
            assert row["flat_assignment_id"]==(246 if upper else 214)+k
            assert row["source"]["line"]==(1416 if upper else 1413)
        pkg="cv32e40p_pkg" if name=="core" else "csr_composition_pkg"
        addr=owner+".csr_addr_i"; en=owner+".csr_we_int"; dst=owner+"."+port
        inhibit=owner+(".mhpmcounter_write_lower" if name=="core" else ".inhibit")
        assert x["target"]==dst and x["address"]==addr and x["enable"]==en
        assert x["enum_type"]==pkg+"::csr_num_e"
        assert x["enum_member"]==("CSR_MCYCLEH" if upper else "CSR_MCYCLE")
        assert x["inhibit"]==(inhibit if upper else None)
        assert x["width_gate"]==({"parameter":pkg+"::MHPMCOUNTER_WIDTH","value":64,"compared_to":64} if upper else None)
        pairs=[{"source":addr,"source_bit":b,"target":dst,"target_bit":k,"role":"comparison_address"} for b in range(12)]+[
            {"source":en,"source_bit":0,"target":dst,"target_bit":k,"role":"write_enable"}]
        if upper: pairs.append({"source":inhibit,"source_bit":k,"target":dst,"target_bit":k,"role":"lower_inhibition"})
        assert x["pairs"]==pairs and x["potential_pairs"]==13+upper
        assert x["model"]=={"address_width":12,"comparison_width":32,"zero_fill_count":20,
            "enum_base":base,"index":k,"comparison_value":base+k,"upper":upper,
            "width_gate":64 if upper else None,"domain":"defined_binary_inputs_only"}
    assert seen==({(p,k) for p in ("mhpmcounter_write_lower","mhpmcounter_write_upper") for k in range(32)} if name!="alu" else set())
    if name=="core":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(3811,1199,64)
        assert ids==set(range(214,278))
    elif name=="alu":
        assert (c["ast_occurrences"],c["historical_rows"],c["supported_residual"])==(612,479,0)
    else:
        assert c["ast_occurrences"]==64 and c["historical_rows"]==64 and ids==set(range(64))


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
        result=audit_csr_composition(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".csr-composition.json")
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
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.csr_composition_pr120",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","input_vectors":16384,"word_checks_per_vector":2,
            "total_checks":32768,"source_sha256":file_sha(FIXTURE)}
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
