"""Run package field-position oracle and census against pinned official RTL."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.packed_members import audit_members
from rtlprep.analysis_budgets import read_ast
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT = Path(__file__).resolve().parents[1]
TOP = "aggregate_pr79"
FIXTURE = ROOT / "tests/fixtures/aggregate_pr79.sv"


def pairs(edges):
    return {(e["source"], e["source_bit"], e["target"], e["target_bit"]) for e in edges}


def check_fixture(result):
    expected = set()
    for i in range(3):
        expected.add((TOP+".high_i", i, TOP+".bundle", i+5))
        expected.add((TOP+".bundle", i+5, TOP+".high_o", i+5))
    for i in range(5):
        expected.add((TOP+".low_i", i, TOP+".bundle", i))
        expected.add((TOP+".bundle", i, TOP+".low_o", i))
    assert result["counts"] == {"sites":4,"supported":4,"partial":0,"edges":16}, result
    assert pairs(result["edges"]) == expected


def check_core(result):
    p = "cv32e40p_core.cs_registers_i."
    # Independent expected offsets from the pinned RTL typedef field order.
    oracle = {
        1055: {(p+"debug_cause_i", i, p+"dcsr_n", i+6) for i in range(3)},
        1059: {(p+"mstatus_q", 5, p+"mstatus_n", 3)},
        1068: {(p+"mstatus_q", 3, p+"mstatus_n", 5)},
        1076: {(p+"dcsr_q", i, p+"priv_lvl_n", i) for i in range(2)},
        1128: {(p+"dcsr_q", 2, p+"debug_single_step_o", 0)},
        1129: {(p+"dcsr_q", 15, p+"debug_ebreakm_o", 0)},
        1130: {(p+"dcsr_q", 12, p+"debug_ebreaku_o", 0)},
    }
    seen = set()
    for row in result["items"]:
        if row["coverage"] != "position_candidates":
            continue
        line = row["source"]["line"]
        assert row["instance"] == p[:-1] and line not in seen and line in oracle, row
        assert pairs(e for e in result["edges"] if e["site_id"] == row["site_id"]) == oracle[line], row
        seen.add(line)
    assert seen == set(oracle), (seen, set(oracle))
    assert result["counts"] == {"sites":30,"supported":7,"partial":23,"edges":10}, result["counts"]


def execute(out):
    out = out.resolve()
    for entry in load_lock():
        root = (ROOT / entry["destination"]).resolve()
        if out == root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=out))
    path, summary = run/"members.result.json", run/"summary.json"
    report = {"status":"incomplete", "cases":[], "design_coverage":"not_measured",
              "functional_influence":"not_proven", "formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        summary.write_text(json.dumps({**report, "cases":[
            {k:v for k,v in c.items() if k not in ("items","edges")} for c in report["cases"]]},
            indent=2), encoding="utf-8")
    save()
    try:
        _, idx = extract(run/"fixture", TOP, [FIXTURE])
        result = audit_members(read_ast(run/"fixture/elaborated_ast.json"), idx)
        report["cases"].append({"name":"fixture", **result})
        save()
        check_fixture(result)
        c,_ = simulate([FIXTURE], TOP, "rtlprep.sim_tests.aggregate_pr79", run/"simulation")
        assert (c["tests"],c["passed"],c["failed"],c["skipped"]) == (1,1,0,0)
        report["fixture_simulation"] = {"status":"passed","vectors":256,"checks":768}
        save()
        d = diagnostics(run/"reference")
        ref = json.loads(d.read_text())
        for name, folder in (("alu", d.parent/"alu"),
                             ("core", Path(ref["core_reference_report"]).parent/"static")):
            ast = read_ast(folder/"elaborated_ast.json")
            idx = json.loads((folder/"rtl_index.json").read_text())
            graph = json.loads((folder/"rtl_dependencies.json").read_text())
            result = audit_members(ast,idx)
            report["cases"].append({"name":name,"source_fingerprint":graph["source_fingerprint"],
                                    "historical_bit_counts":graph["bit_dependency_graph"]["counts"],**result})
            save()
            if name == "core":
                check_core(result)
            else:
                assert result["counts"] == {"sites":0,"supported":0,"partial":0,"edges":0}
            assert not graph["analysis_limits"]["truncated_analyzers"]
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(f"Summary: {summary}",flush=True)
        print(summary.read_text(),flush=True)
    return path


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    execute(p.parse_args().out)
