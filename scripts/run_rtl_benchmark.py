"""Benchmark RISC-V/RTLPrep reproductible avec slang réel, sans modèle LLM.

Le programme distingue mesure de contexte/temps, classification sur un
sous-ensemble d'arêtes étiquetées et évaluation d'un agent (hors périmètre).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from rtlprep.benchmark import evaluate_case
from rtlprep.manifest import load_design

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "benchmarks/rtl_questions_v1.json"


def run(*, out: Path, repeat: int = 3, timeout: int = 180,
        cpu_manifest: Path | None = None) -> dict:
    out = out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if shutil.which("slang") is None:
        raise RuntimeError("slang réel absent : aucun chiffre simulé ne sera publié")
    doc = json.loads(LABELS.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise ValueError("Jeu d'étiquettes non compatible")
    cases = {}
    for item in doc["cases"]:
        design = load_design(ROOT / item["manifest"])
        data = evaluate_case(design, out / item["name"], name=item["name"],
                             labels=item, repeat=repeat, timeout=timeout)
        cases[item["name"]] = data
        scored = data["labelled_edges"]
        if scored["fn"] or scored["fp"]:
            raise AssertionError(
                f"{item['name']}: labels contradictoires au graphe réel: {scored}"
            )
        for question in data["queries"]:
            if question["missing_reachable"]:
                raise AssertionError(
                    f"{item['name']}/{question['id']}: chemins attendus absents: "
                    f"{question['missing_reachable']}"
                )
    if cpu_manifest is not None:
        # La chaîne d'élaboration de l'ALU a été testée séparément dans
        # scripts/run_cv32e40p_alu.py, avec commit/empreintes vérifiés.
        d = load_design(cpu_manifest.expanduser().resolve())
        if d.top != "cv32e40p_alu":
            raise ValueError("Le benchmark CPU attend le top cv32e40p_alu")
        cpu_labels = {
            "top": "cv32e40p_alu",
            "questions": [
                {"id": "cpu_result", "question": "Quelles entrées peuvent influencer le résultat ALU ?",
                 "target": "cv32e40p_alu.result_o"},
                {"id": "cpu_comparison", "question": "Quelles entrées peuvent influencer la comparaison ALU ?",
                 "target": "cv32e40p_alu.comparison_result_o"},
            ],
        }
        cases["cv32e40p_alu"] = evaluate_case(
            d, out / "cv32e40p_alu", name="cv32e40p_alu",
            labels=cpu_labels, repeat=repeat, timeout=timeout,
        )
    all_metrics = [case["labelled_edges"] for case in cases.values()
                   if case["labelled_edges"] is not None]
    total = {
        key: sum(m[key] for m in all_metrics)
        for key in ("tp", "fn", "fp", "tn", "positive_labels", "negative_labels",
                    "unlabelled_edges")
    }
    total["precision_on_labels"] = round(
        total["tp"] / (total["tp"] + total["fp"]), 4
    ) if total["tp"] + total["fp"] else None
    total["recall_on_labels"] = round(
        total["tp"] / (total["tp"] + total["fn"]), 4
    ) if total["tp"] + total["fn"] else None
    questions = [x for case in cases.values() for x in case["queries"]]
    sizes = {key: sum(x["payload_bytes"][key] for x in questions)
             for key in ("A_raw", "B_index", "C_hybrid")}
    report = {
        "schema_version": 1,
        "method": "offline_deterministic_evidence_and_context_benchmark",
        "validated_llm_accuracy": False,
        "benchmarked_real_llm": False,
        "uses_paid_api": False,
        "slang": subprocess.run(["slang", "--version"], text=True,
                                capture_output=True, check=True).stdout.strip(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "label_file": LABELS.relative_to(ROOT).as_posix(),
        "labels_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest(),
        "repeat": repeat,
        "cases": cases,
        "aggregate_labelled": total,
        "aggregate_payload_bytes": sizes,
        "aggregate_hybrid_vs_raw": round(
            sizes["C_hybrid"] / sizes["A_raw"], 4
        ) if sizes["A_raw"] else None,
        "caveats": [
            "Les 35 positifs / 16 négatifs sont un sous-ensemble manuel, pas une vérité exhaustive.",
            "Les 3 stratégies construisent des charges utiles, PAS des réponses de LLM.",
            "Les octets JSON et mots séparés par espace ne sont pas des tokens réels.",
            "Les durées sur runner CI sont bruitées ; ne pas en déduire une accélération universelle.",
            "A/B/C ne sont pas une comparaison d'exactitude des réponses sans agent.",
            "Les avertissements, les troncatures et la granularité signal doivent être visibles.",
        ],
    }
    file = out / "benchmark_report.json"
    file.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print(json.dumps({
        "report": str(file), "slang": report["slang"],
        "cases": {k: {
            "timing_median_ms": v["timing"]["median_ms"],
            "counts": v["counts"],
            "labelled": v["labelled_edges"] and {
                key: v["labelled_edges"][key] for key in ("tp", "fn", "fp", "tn")
            },
        } for k, v in cases.items()},
        "aggregate_labelled": total,
        "aggregate_payload_bytes": sizes,
        "hybrid_vs_raw": report["aggregate_hybrid_vs_raw"],
        "notice": "PAS un test de qualité de réponses Codex/ChatGPT.",
    }, indent=2, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("reports/benchmark"))
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cpu-manifest", type=Path,
                        help="Manifeste de l'ALU officielle préparé avec le script CV32E40P")
    args = parser.parse_args()
    run(out=args.out, repeat=args.repeat, timeout=args.timeout,
        cpu_manifest=args.cpu_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
