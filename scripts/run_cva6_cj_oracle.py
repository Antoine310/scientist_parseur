"""Simulate the genuine pinned OpenHW CVA6 c.j branch, with a negative mutant.

Never copies upstream RTL into this repository. Uses verified sparse checkout
bytes, and writes the deliberately altered file ONLY into the output directory.
All interpretation is limited to the RISC-V c.j branch, two-state simulations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from rtlprep.simulation import parse_cocotb_results
from scripts.run_cva6_compressed_decoder import (
    TOP, UPSTREAM_COMMIT, UPSTREAM_REPOSITORY, WRAPPER, verify_pinned_sources,
)

TEST_MODULE = "rtlprep.sim_tests.cva6_cj_official"
MUTATION_OLD = "              ~instr_i[15],\n              riscv::OpcodeJal"
MUTATION_NEW = "              instr_i[15],\n              riscv::OpcodeJal"


def mutate_decoder(original: str) -> str:
    """Single exact, reviewed mutation of the official c.j field."""
    if original.count(MUTATION_OLD) != 1:
        raise ValueError("pinned c.j BitwiseNot anchor missing or duplicated")
    altered = original.replace(MUTATION_OLD, MUTATION_NEW, 1)
    if altered == original or altered.replace(MUTATION_NEW, MUTATION_OLD, 1) != original:
        raise ValueError("mutant differs beyond the approved c.j inversion")
    return altered


def _oracle_failure_evidence(xml: Path) -> bool:
    """An actual cocotb assertion on the inverted output bit, not a build error."""
    tree = ElementTree.parse(xml)
    failures = tree.findall(".//failure")
    return bool(failures) and any(
        "PR42_CJ_VALUE_MISMATCH" in (str(el.attrib) + " " + (el.text or ""))
        and "bit7_diff=1" in (str(el.attrib) + " " + (el.text or ""))
        for el in failures
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source_root: Path, output: Path, variant: str) -> tuple[int, dict]:
    if variant not in ("gold", "mutant"):
        raise ValueError("variant must be gold or mutant")
    root, out = source_root.resolve(), output.resolve()
    if (out == root or out.is_relative_to(root) or
            root.is_relative_to(out)):
        raise ValueError("output directory must not touch the pinned source tree")
    sources, revision_status = verify_pinned_sources(root)
    if revision_status != "verified_exact_commit":
        raise ValueError("a verified Git checkout is required, not loose copied blobs")
    if not WRAPPER.is_file():
        raise ValueError("reviewed RTLPrep CVA6 wrapper missing")

    upstream_file = root / "core/compressed_decoder.sv"
    gold_original = upstream_file.read_text(encoding="utf-8")
    source_githash = _sha256(upstream_file)
    chosen_sources = list(sources)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "schema_version": 1, "project": "OpenHW CVA6",
        "upstream": UPSTREAM_REPOSITORY, "upstream_commit": UPSTREAM_COMMIT,
        "configuration": "cv32a6_imac_sv32", "top": TOP,
        "variant": variant, "source_integrity": "verified_pinned_git_blobs",
        "checkout_revision_status": revision_status,
        "gold_source_sha256": source_githash,
        "mutant_sha256": None, "mutation_applied": variant == "mutant",
        "simulator": "verilator", "oracle": TEST_MODULE,
        "oracle_independent_of_rtlprep_ast": True,
        "scope": "c.j C1/101 subset; two-state sample, not full CVA6",
        "design_coverage": "not_measured",
        "functional_correctness_of_entire_cva6": "not_tested",
        "accuracy": "not_measured_without_independent_exhaustive_oracle",
        "status": "not_run", "passed": 0, "failed": 0, "skipped": 0, "tests": 0,
    }
    report_path = out / "cva6_cj_simulation.result.json"
    xml = out / "simulation_results.xml"
    xml.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)

    if variant == "mutant":
        altered = mutate_decoder(gold_original)
        mutated = out / "generated" / "compressed_decoder.sv"
        mutated.parent.mkdir(parents=True, exist_ok=True)
        mutated.write_text(altered, encoding="utf-8")
        report["mutant_sha256"] = _sha256(mutated)
        if report["mutant_sha256"] == source_githash:
            raise ValueError("mutation did not alter the pinned source")
        chosen_sources[-1] = mutated
    chosen_sources.append(WRAPPER.resolve())

    try:
        from cocotb_tools.runner import get_runner

        runner = get_runner("verilator")
        runner.build(
            sources=chosen_sources,
            includes=[root / "core/include"],
            defines={},
            hdl_toplevel=TOP,
            build_dir=out / "simulation_build",
            build_args=["--timing", "-Wno-fatal"],
            timescale=("1ns", "1ps"), always=True, clean=True,
        )
        runner.test(
            hdl_toplevel=TOP, test_module=TEST_MODULE,
            build_dir=out / "simulation_build", test_dir=out,
            results_xml=str(xml), timescale=("1ns", "1ps"),
        )
    except (Exception, SystemExit) as exc:
        report["simulator_exception"] = f"{type(exc).__name__}: {str(exc)[:500]}"

    if xml.is_file():
        try:
            report.update(parse_cocotb_results(xml))
            report["mutation_failure_evidence"] = _oracle_failure_evidence(xml)
        except (ElementTree.ParseError, OSError, ValueError) as exc:
            report["xml_error"] = str(exc)[:500]

    # Exit codes and reports distinguish the positive test from an
    # intentionally failing *oracle assertion* on the negative control.
    report["status"] = "failed"
    if (variant == "gold" and report["tests"] == 3 and
            report["passed"] == 3 and report["failed"] == 0 and
            report["skipped"] == 0 and
            "simulator_exception" not in report):
        report["status"] = "passed"
        code = 0
    elif (variant == "mutant" and report["tests"] == 3 and
          report["failed"] >= 1 and report["skipped"] == 0 and
          report.get("mutation_failure_evidence") is True):
        report["status"] = "expected_mutation_failure"
        code = 2
    else:
        code = 1
    # Preserve all data even for a broken simulator/build.
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    verify_pinned_sources(root)
    if _sha256(upstream_file) != source_githash:
        raise ValueError("official CVA6 bytes changed during simulation")
    print("PR42_PINNED_CVA6_CJ_SIM_RESULT",
          json.dumps({k: report[k] for k in (
              "variant", "status", "tests", "passed", "failed",
              "source_integrity", "checkout_revision_status",
          )}, sort_keys=True))
    return code, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variant", choices=("gold", "mutant"), required=True)
    args = parser.parse_args()
    code, _ = run(args.source_root, args.out, args.variant)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
