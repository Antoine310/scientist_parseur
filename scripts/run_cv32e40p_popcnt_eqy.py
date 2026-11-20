"""Benchmark EQY sur le véritable popcount CV32E40P de OpenHW.

Avant exécution, récupérer le dépôt OpenHW à la révision épinglée :
  python scripts/run_cv32e40p_popcnt_eqy.py --source-root upstream_cv32e40p

Deux variantes sont écrites uniquement sous --out : une refactorisation
commutative + et un mutant incorrect -. Les fichiers du CPU ne sont
jamais modifiés dans le checkout amont ni copiés dans le dépôt RTLPrep.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from rtlprep.equivalence import (
    POPCNT_GOLD_BLOB, equivalence_check, git_blob_digest, popcnt_variant,
)
from rtlprep.manifest import load_design

UPSTREAM_REPO = "openhwfoundation/cv32e40p"
UPSTREAM_COMMIT = "b353438ff469c030c89f6804f3b24a2852880e8b"
RELATIVE_SOURCE = "rtl/cv32e40p_popcnt.sv"
TOP = "cv32e40p_popcnt"
VARIANTS = {
    "refactored": ("cv32e40p_popcnt_refactored.sv", True),
    "buggy": ("cv32e40p_popcnt_buggy.sv", False),
}


def make_manifest(path: Path, source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"top": TOP, "sources": [str(source.resolve())],
                    "include_dirs": [], "defines": []}, indent=2),
        encoding="utf-8",
    )


def run_experiment(source_root: Path, out: Path, timeout: int = 180) -> dict:
    source_root = source_root.expanduser().resolve()
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if timeout < 1:
        raise ValueError("Timeout EQY incorrect")
    source = source_root / RELATIVE_SOURCE
    if not source.is_file():
        raise FileNotFoundError(f"RTL OpenHW non trouvé : {source}")
    original_bytes = source.read_bytes()
    git_blob = git_blob_digest(original_bytes)
    if git_blob != POPCNT_GOLD_BLOB:
        raise ValueError(
            f"Source OpenHW différente du blob Git épinglé : "
            f"obtenu {git_blob}, attendu {POPCNT_GOLD_BLOB}"
        )
    upstream_head = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    if upstream_head != UPSTREAM_COMMIT:
        raise ValueError(f"Révision OpenHW incorrecte : {upstream_head}")

    gold_manifest = out / "gold.json"
    make_manifest(gold_manifest, source)
    gold = load_design(gold_manifest)
    summary: dict = {
        "project": "OpenHW CV32E40P",
        "repository": UPSTREAM_REPO, "upstream_commit": UPSTREAM_COMMIT,
        "source": RELATIVE_SOURCE,
        "git_blob": POPCNT_GOLD_BLOB,
        "source_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "top": TOP, "variants": {},
        "interpretation": (
            "EQY compares these two versions under Yosys semantics. "
            "It does not prove the original CPU module meets its specification."
        ),
    }
    for label, (filename, expected_equivalent) in VARIANTS.items():
        pair_out = out / label
        pair_out.mkdir(parents=True, exist_ok=True)
        candidate = pair_out / filename
        candidate.write_bytes(
            popcnt_variant(original_bytes.decode("utf-8"), filename=filename)
            .encode("utf-8")
        )
        gate_manifest = pair_out / "gate.json"
        make_manifest(gate_manifest, candidate)
        verdict = equivalence_check(gold, load_design(gate_manifest), pair_out,
                                    timeout=timeout)
        summary["variants"][label] = {
            "expected_equivalent": expected_equivalent,
            "status": verdict["status"],
            "equivalent": verdict["equivalent"],
            "partitions": verdict["partition_count"],
            "trace_files": verdict["trace_files"],
            "result_file": str(pair_out / "equivalence.result.json"),
            "error": verdict.get("error"),
        }
        if expected_equivalent:
            if not (verdict["status"] == "passed"
                    and verdict["equivalent"] is True
                    and verdict["partition_count"] > 0):
                raise AssertionError(f"Refactorisation non prouvée : {verdict}")
        else:
            if not (verdict["status"] == "failed"
                    and verdict["equivalent"] is False
                    and verdict["partition_count"] > 0
                    and verdict["trace_files"]
                    and all(Path(p).is_file() for p in verdict["trace_files"])):
                raise AssertionError(f"Mutant non réfuté avec trace : {verdict}")

    (out / "cv32e40p_popcnt_eqy_report.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("reports/cv32e40p-popcnt-eqy"))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run_experiment(args.source_root, args.out, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
