"""Consolide les preuves réellement produites par slang, cocotb, SBY, EQY.

Aucun résultat n'est inventé : les statuts sont lus depuis les fichiers
générés par les commandes EDA de la CI. Le graphe seul ne peut pas prouver
la condition booléenne de contrôle d'accès.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rtlprep.dependencies import trace_dependencies

TOP = "secure_csr"
SOURCE_INPUTS = {f"{TOP}.write_i", f"{TOP}.machine_mode_i",
                 f"{TOP}.debug_locked_i"}
REGISTER_INPUTS = SOURCE_INPUTS | {f"{TOP}.wdata_i"}


def load(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Preuve absente : {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Rapport invalide : {path}")
    return data


def graph_signature(graph: dict) -> list[list[str]]:
    return sorted({(e["source"], e["target"], e["kind"])
                   for e in graph["edges"]})


def verify(root: Path) -> dict:
    root = root.resolve()
    gold = load(root / "rtl-gold/rtl_dependencies.json")
    buggy = load(root / "rtl-buggy/rtl_dependencies.json")
    if gold["top"] != TOP or buggy["top"] != TOP:
        raise AssertionError("Le laboratoire ne vérifie pas le bon top")
    if not gold["edges"] or not buggy["edges"]:
        raise AssertionError("Graphe RTL vide")
    traces = {}
    for name, graph in (("gold", gold), ("buggy", buggy)):
        for target, expected in (
            (f"{TOP}.write_accepted_o", SOURCE_INPUTS),
            (f"{TOP}.value_o", REGISTER_INPUTS),
        ):
            trace = trace_dependencies(graph, target, "fanin",
                                       max_depth=6, max_edges=80)
            if trace["truncated"]:
                raise AssertionError(f"Trace tronquée : {name}/{target}")
            missing = expected - set(trace["visited_nodes"])
            if missing:
                raise AssertionError(f"Influences absentes : {name}/{target} {missing}")
            traces[f"{name}/{target}"] = {
                "visited_nodes": trace["visited_nodes"],
                "edge_count": len(trace["edges"]),
                "warnings": len(trace["graph_warnings"]),
            }

    sim_good = load(root / "sim-gold/simulation.result.json")
    sim_bad = load(root / "sim-buggy/simulation.result.json")
    formal_good = load(root / "formal-gold/formal.result.json")
    formal_bad = load(root / "formal-buggy/formal.result.json")
    eqy_good = load(root / "eqy-good/equivalence.result.json")
    eqy_bad = load(root / "eqy-buggy/equivalence.result.json")

    if not (sim_good["status"] == "passed"
            and sim_good["tests"] == sim_good["passed"] == 3
            and sim_good["failed"] == 0):
        raise AssertionError(f"Simulation saine invalide : {sim_good}")
    if not (sim_bad["status"] == "failed"
            and sim_bad["failed"] >= 1 and sim_bad["tests"] == 3
            and any(t["status"] == "failed" and
                    "unprivileged" in str(t["name"])
                    for t in sim_bad["testcases"])):
        raise AssertionError(f"Contrôle négatif cocotb invalide : {sim_bad}")
    if not (formal_good["status"] == "passed"
            and formal_good["proof"]["sby_status"] == "PASS"
            and formal_good["cover"]["sby_status"] == "PASS"):
        raise AssertionError(f"Preuve saine ou témoin absents : {formal_good}")
    if not (formal_bad["status"] == "failed"
            and formal_bad["proof"]["sby_status"] == "FAIL"
            and formal_bad["proof"]["trace_files"]):
        raise AssertionError(f"Contre-exemple SBY absent : {formal_bad}")
    if not (eqy_good["status"] == "passed" and eqy_good["equivalent"] is True
            and eqy_good["partition_count"] > 0):
        raise AssertionError(f"Équivalence bonne refactorisation absente : {eqy_good}")
    if not (eqy_bad["status"] == "failed" and eqy_bad["equivalent"] is False
            and eqy_bad["eqy_verdict"] == "FAIL"
            and eqy_bad["trace_files"]):
        raise AssertionError(f"Non-équivalence sans témoin EQY : {eqy_bad}")
    sby_traces = formal_bad["proof"]["trace_files"]
    eqy_traces = eqy_bad["trace_files"]
    if not all(Path(path).is_file() for path in sby_traces + eqy_traces):
        raise AssertionError("Traces VCD manquantes sur le disque")

    signatures_equal = graph_signature(gold) == graph_signature(buggy)
    report = {
        "schema_version": 1,
        "scenario": "RISC-V-inspired protected CSR authorization (synthetic lab)",
        "benchmark_real_agent": False,
        "bug_introduced_intentionally": True,
        "threat_model": (
            "Unprivileged user write when debug is not locked. "
            "This is a training design, not a demonstrated CV32E40P vulnerability."
        ),
        "sources": {
            "gold_fingerprint": gold["source_fingerprint"],
            "buggy_fingerprint": buggy["source_fingerprint"],
        },
        "graph": {
            "gold_edges": len(gold["edges"]),
            "buggy_edges": len(buggy["edges"]),
            "typed_edge_sets_equal": signatures_equal,
            "warnings": {"gold": len(gold["warnings"]),
                         "buggy": len(buggy["warnings"])},
            "traces": traces,
            "conclusion": (
                "Un graphe au niveau signal repère les influences mais ne "
                "démontre PAS le prédicat booléen d'autorisation. "
                "Une signature d'arêtes égale ne garantit jamais "
                "l'équivalence des comportements."
            ),
        },
        "simulation": {
            "gold": {"status": sim_good["status"], "passed": sim_good["passed"]},
            "buggy": {"status": sim_bad["status"], "failed": sim_bad["failed"],
                      "testcases": sim_bad["testcases"]},
        },
        "formal": {
            "gold_proof": formal_good["proof"]["sby_status"],
            "gold_cover": formal_good["cover"]["sby_status"],
            "buggy_proof": formal_bad["proof"]["sby_status"],
            "counterexample_files": sby_traces,
        },
        "equivalence": {
            "good": eqy_good["eqy_verdict"],
            "bad": eqy_bad["eqy_verdict"],
            "good_partitions": eqy_good["partition_count"],
            "bad_partitions": eqy_bad["partition_count"],
            "counterexample_files": eqy_traces,
        },
        "conclusion": (
            "La vulnérabilité intentionnelle est détectée sur cet exemple "
            "par cocotb, SBY et EQY. Aucun agent IA autonome n'a été évalué."
        ),
    }
    (root / "security_lab_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "report": str(root / "security_lab_report.json"),
        "graphs_identical": signatures_equal,
        "simulation_bug_failures": sim_bad["failed"],
        "formal_good": formal_good["proof"]["sby_status"],
        "formal_buggy": formal_bad["proof"]["sby_status"],
        "eqy_good": eqy_good["eqy_verdict"],
        "eqy_buggy": eqy_bad["eqy_verdict"],
        "sby_counterexamples": len(sby_traces),
        "eqy_counterexamples": len(eqy_traces),
    }, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("reports/security-lab"))
    args = parser.parse_args()
    verify(args.root)
