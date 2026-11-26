"""Real aggregate census on fixture, pinned ALU and core; separate from graph."""
import argparse
import json
from pathlib import Path
import tempfile

from rtlprep.aggregate_layout import audit
from rtlprep.analysis_budgets import read_ast
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT = Path(__file__).resolve().parents[1]
TOP = "aggregate_pr78"
FIXTURE = ROOT / "tests/fixtures/aggregate_pr78.sv"


def check_fixture(result):
    c = result["counts"]
    assert c["lhs_concat"] == 1 and c["supported"] == 1 and c["edges"] == 8, result
    assert c["lhs_member"] >= 1 and c["rhs_member"] >= 3, result
    actual = {(e["source"], e["source_bit"], e["target"], e["target_bit"])
              for e in result["edges"]}
    expected = ({(TOP+".data", i, TOP+".concat_lo", i) for i in range(5)} |
                {(TOP+".data", i+5, TOP+".concat_hi", i) for i in range(3)})
    assert actual == expected, (actual, expected)
    assert all(r["coverage"] == "partial" for r in result["items"]
               if r["lhs_members"] or r["rhs_members"])


def execute(out):
    out = out.resolve()
    for entry in load_lock():
        root = (ROOT / entry["destination"]).resolve()
        if out == root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=out))
    path = run / "aggregate.result.json"
    summary = run / "summary.json"
    report = {"status": "incomplete", "cases": [], "design_coverage": "not_measured",
              "functional_influence": "not_proven", "formal_proof": "not_performed"}
    def save():
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        summary.write_text(json.dumps({**report, "cases": [
            {k:v for k,v in c.items() if k not in ("items", "edges")}
            for c in report["cases"]]}, indent=2), encoding="utf-8")
    save()
    try:
        _, idx = extract(run / "fixture", TOP, [FIXTURE])
        fixture = audit(read_ast(run / "fixture/elaborated_ast.json"), idx)
        report["cases"].append({"name": "fixture", **fixture})
        save()
        check_fixture(fixture)
        counts, _ = simulate([FIXTURE], TOP, "rtlprep.sim_tests.aggregate_pr78", run / "simulation")
        assert (counts["tests"], counts["passed"], counts["failed"], counts["skipped"]) == (1,1,0,0)
        report["fixture_simulation"] = {"status": "passed", "vectors": 256, "checks": 1280}
        save()
        d = diagnostics(run / "reference")
        reference = json.loads(d.read_text())
        for name, folder in (("alu", d.parent / "alu"),
                             ("core", Path(reference["core_reference_report"]).parent / "static")):
            ast = read_ast(folder / "elaborated_ast.json")
            idx = json.loads((folder / "rtl_index.json").read_text())
            graph = json.loads((folder / "rtl_dependencies.json").read_text())
            result = audit(ast, idx)
            expected = next(c for c in reference["cases"] if c["top"] == idx["top"])
            assert result["assignment_ast_occurrences"] == expected["syntax_census"]["assignment_count"]
            assert not graph["analysis_limits"]["truncated_analyzers"]
            report["cases"].append({"name": name, "source_fingerprint": graph["source_fingerprint"],
                                    "historical_bit_counts": graph["bit_dependency_graph"]["counts"],
                                    **result})
            save()
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(f"Summary: {summary}", flush=True)
        print(summary.read_text(), flush=True)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    execute(parser.parse_args().out)
