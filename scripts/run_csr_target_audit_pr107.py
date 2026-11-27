"""Exact reconciliation of historical target refusals with existing evidence."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha, INPUTS
from rtlprep.csr_target_audit import audit_targets
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.cv32e40p_pr67 import ast_inventory

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"tests/fixtures/csr_target_audit_pr107.sv"
FIXTURE_TOP=FIXTURE.stem


def extract_fixture(directory):
    return extract(directory,FIXTURE_TOP,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(4,2,2,2),"alu":(0,0,0,0),"core":(5,3,3,2),
              "axis_register":(0,0,0,0),"priority_encoder":(0,0,0,0),"rxuart":(2,0,0,2)}
    assert tuple(c[k] for k in ("historical_unsupported_targets","existing_position_occurrences",
                                "existing_position_records","without_linked_member_positions"))==expected[name],c
    assert c["new_records"]==c["new_edges"]==0 and result["historical_replay_exact"]
    assert not result["historical_graph_promoted"]
    if name not in ("fixture","core"):
        return
    owner="csr_target_audit_pr107" if name=="fixture" else "cv32e40p_core.cs_registers_i"
    member_expected={"flag_a":(3,1),"flag_b":(1,0)} if name=="fixture" else {"ebreakm":(15,15),"stepie":(11,11),"step":(2,2)}
    scope_expected={"gen_regs.flag_q","gen_regs.word_q"} if name=="fixture" else {"gen_trigger_regs.tmatch_control_exec_q","gen_trigger_regs.tmatch_value_q"}
    got_members={}
    got_scopes=set()
    for row in result["items"]:
        assert row["instance"]==owner and row["historical_flat_assignment_id"] is None
        if row["reason"]=="member_access_outside_legacy_target_gate":
            assert len(row["existing_typed_positions"])==1
            p=row["existing_typed_positions"][0]
            assert p["producer"]=="pr80" and p["target"]["field"]==row["field"]
            assert p["source"]["signal"]==owner+(".data" if name=="fixture" else ".csr_wdata_int")
            assert p["target"]["signal"]==owner+(".bundle" if name=="fixture" else ".dcsr_n")
            assert p["source"]["coordinate_kind"]=="declared_index" and p["target"]["coordinate_kind"]=="packed_struct_offset"
            assert row["field"] not in got_members
            got_members[row["field"]]=(p["source"]["position"],p["target"]["position"])
        else:
            assert row["reason"]=="generate_scoped_target_outside_legacy_flat_gate"
            assert not row["existing_member_record_ids"] and row["context"]=="AlwaysFF"
            got_scopes.add(row["exact_target"].removeprefix(owner+"."))
    assert got_members==member_expected and got_scopes==scope_expected,(got_members,got_scopes)
    if name=="core":
        assert {r["source"]["line"] for r in result["items"]}=={999,1002,1006,1272,1273}


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
            "functional_influence":"not_proven","formal_proof":"not_applicable_to_syntax_audit"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,upstream=None):
        before={k:file_sha(folder/k) for k in INPUTS}
        ast=read_ast(folder/INPUTS[0])
        idx=json.loads((folder/INPUTS[1]).read_text())
        graph=json.loads((folder/INPUTS[2]).read_text())
        start=perf_counter()
        result=audit_targets(ast,idx,graph)
        elapsed=perf_counter()-start
        detail=run/(name+".csr-target-audit.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        prior=ast_inventory(ast,{r["path"]:r["module"] for r in idx["instances"]})
        assert prior["assignment_count"]==result["counts"]["ast_occurrences"]
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"status":"passed","input_sha256":before,
             "detail_file":detail.name,"detail_sha256":file_sha(detail),"audit_seconds":elapsed,
             "upstream":upstream,"historical_unchanged":True,"pr67_census_reconciled":True,
             **{k:v for k,v in result.items() if k not in ("items",)}})
        save()
    try:
        extract_fixture(run/"fixture")
        case("fixture",run/"fixture")
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
        for e in lock:
            if e["repository"] not in ("alexforencich/verilog-axis","ZipCPU/wbuart32"):
                continue
            root=ROOT/e["destination"]
            verify_checkout(root,e)
            for src in e["blobs"]:
                name=Path(src).stem
                folder=run/name
                extract(folder,name,[root/src])
                case(name,folder,{"repository":e["repository"],"commit":e["commit"],"blob":e["blobs"][src]})
            verify_checkout(root,e)
        assert len(report["cases"])==6
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
    args=p.parse_args()
    execute(args.out,args.reference)
