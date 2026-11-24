"""Run pinned CVA6 multi-family behavioral tests with isolated mutants."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree
from rtlprep.simulation import parse_cocotb_results
from rtlprep.cva6_compressed_reference import expected
from scripts.run_cva6_compressed_decoder import (
    TOP, UPSTREAM_COMMIT, UPSTREAM_REPOSITORY, WRAPPER, verify_pinned_sources,
)

TEST_MODULE = "rtlprep.sim_tests.cva6_compressed_official"
# Exact, branch-local anchors, preserving width. Values are output XOR masks.
MUTATIONS = {
    "addi": ("OpcodeC1Addi", "{6{instr_i[12]}}", "{6{~instr_i[12]}}", 0xFC000000),
    "addi4spn": ("OpcodeC0Addi4spn", "instr_i[6],", "~instr_i[6],", 0x00400000),
    "lw": ("OpcodeC0Lw", "instr_i[5],", "~instr_i[5],", 0x04000000),
    "sw": ("OpcodeC0Sw", "instr_i[6],", "~instr_i[6],", 0x00000200),
}

def mutate_decoder(original, family):
    label, old, new, _ = MUTATIONS[family]
    anchor = "          riscv::" + label + ": begin"
    if original.count(anchor) != 1:
        raise ValueError("missing or duplicated branch anchor")
    start = original.index(anchor)
    end = original.index("\n          end", start)
    block = original[start:end]
    if block.count(old) != 1 or new in block:
        raise ValueError("missing or duplicated mutation anchor")
    return original[:start] + block.replace(old, new, 1) + original[end:]

def _oracle_failure_evidence(xml, family):
    mask = MUTATIONS[family][3]
    failures = ElementTree.parse(xml).findall(".//failure")
    if len(failures) != 1:
        return False
    el = failures[0]
    msg = str(el.attrib) + " " + (el.text or "")
    match = re.search(r"PR44_VALUE_MISMATCH family=(\w+) class=valid input=0x([0-9a-f]{8}) expected=0x([0-9a-f]{8}) actual=0x([0-9a-f]{8}) xor=0x([0-9a-f]{8})", msg)
    if not match or match[1] != family:
        return False
    word, want, actual, difference = (int(x, 16) for x in match.groups()[1:])
    ref = expected(word)
    return ref.family == family and ref.classification == "valid" and ref.instruction == want and (want ^ actual) == difference == mask

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source_root: Path, output: Path, variant: str) -> tuple[int, dict]:
    if variant not in ("gold", *MUTATIONS):
        raise ValueError("invalid variant")
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
        "mutant_sha256": None, "mutation_applied": variant != "gold",
        "simulator": "verilator", "oracle": TEST_MODULE,
        "oracle_independent_of_rtlprep_ast": True,
        "scope": "C.ADDI/C.NOP, C.ADDI4SPN, C.LW, C.SW; two-state",
        "design_coverage": "not_measured",
        "functional_correctness_of_entire_cva6": "not_tested",
        "accuracy": "not_measured_without_independent_exhaustive_oracle",
        "planned_low_halfword_patterns": 8192,
        "planned_stimulus_vectors": 9216,
        "expected_mutation_xor": MUTATIONS[variant][3] if variant != "gold" else None,
        "status": "not_run", "passed": 0, "failed": 0, "skipped": 0, "tests": 0,
    }
    report_path = out / "cva6_compressed_simulation.result.json"
    xml = out / "simulation_results.xml"
    xml.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)

    if variant != "gold":
        altered = mutate_decoder(gold_original, variant)
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
            report["mutation_failure_evidence"] = _oracle_failure_evidence(xml, variant) if variant != "gold" else False
        except (ElementTree.ParseError, OSError, ValueError) as exc:
            report["xml_error"] = str(exc)[:500]

    # Exit codes and reports distinguish the positive test from an
    # intentionally failing *oracle assertion* on the negative control.
    report["status"] = "failed"
    if (variant == "gold" and report["tests"] == 4 and
            report["passed"] == 4 and report["failed"] == 0 and
            report["skipped"] == 0 and
            "simulator_exception" not in report):
        report["status"] = "passed"
        code = 0
    elif (variant != "gold" and report["tests"] == 4 and
          report["failed"] == 1 and report["passed"] == 3 and report["skipped"] == 0 and
          report.get("mutation_failure_evidence") is True and
          "simulator_exception" not in report and "xml_error" not in report):
        report["status"] = "expected_mutation_failure"
        code = 2
    else:
        code = 1
    report["completed_stimulus_vectors"] = 9216 if code == 0 else None
    # Preserve all data even for a broken simulator/build.
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    verify_pinned_sources(root)
    if _sha256(upstream_file) != source_githash:
        raise ValueError("official CVA6 bytes changed during simulation")
    print("PR44_PINNED_CVA6_SIM_RESULT",
          json.dumps({k: report[k] for k in (
              "variant", "status", "tests", "passed", "failed",
              "source_integrity", "checkout_revision_status",
          )}, sort_keys=True))
    return code, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variant", choices=("gold", *MUTATIONS), required=True)
    args = parser.parse_args()
    code, _ = run(args.source_root, args.out, args.variant)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
