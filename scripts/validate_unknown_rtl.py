"""Reproducible evaluation of third-party pinned RTL (no LLM and no proofs).

Requires real slang and separate local checkouts matching suite pins:
  python scripts/validate_unknown_rtl.py --sources-root upstream_unknown
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from rtlprep.field_validation import run_suite

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "benchmarks/unknown_designs_v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE,
                        help="pinned external case manifest")
    parser.add_argument("--sources-root", type=Path, required=True,
                        help="parent directory containing verified upstream checkouts")
    parser.add_argument("--out", type=Path, default=Path("reports/unknown-validation"))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--case", action="append", dest="cases",
                        help="optional subset of case ids (repeatable)")
    args = parser.parse_args(argv)
    if not shutil.which("slang"):
        parser.exit(2, "slang absent : impossible de mesurer un vrai RTL inconnu\n")
    try:
        suite = json.loads(args.suite.read_text(encoding="utf-8"))
        report = run_suite(
            suite, sources_root=args.sources_root,
            output=args.out, timeout=args.timeout,
            selected=set(args.cases) if args.cases else None,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Validation impossible : {exc}\n")
    print(json.dumps({
        "report": str((args.out / "unknown_validation_report.json").resolve()),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "slang": subprocess.run(["slang", "--version"], capture_output=True,
                                text=True, check=True).stdout.strip(),
        "cases": [
            {
                "id": x["id"], "status": x["status"], "execution": x["execution"],
                "source_integrity": x["source_integrity"],
                "warnings": x.get("audit", {}).get("warning_count"),
                "all_probes_present": x.get("audit", {}).get("all_probes_present"),
            }
            for x in report["cases"]
        ],
        "all_elaborated": report["all_elaborated"],
        "all_probes_present": report["all_probes_present"],
        "accuracy": report["accuracy"],
        "benchmarked_llm": report["benchmarked_llm"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["all_elaborated"] and report["all_probes_present"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
