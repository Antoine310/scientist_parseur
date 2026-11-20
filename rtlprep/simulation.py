"""Simulation comportementale cocotb/Verilator et rapports de tests fiables.

Le banc de test est une *liste blanche* de modules revus dans RTLPrep,
jamais une expression Python ou une commande tirée d'un manifeste non fiable.
La simulation exige explicitement cocotb et Verilator ; elle n'est pas formelle.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

from .manifest import Design
from .runner import fingerprint, run_command


# Testbenches revus et inclus dans le paquet. Pas de Python provenant du RTL.
TEST_SUITES = {
    "counter": "rtlprep.sim_tests.counter",
    "handshake_fsm": "rtlprep.sim_tests.handshake_fsm",
}


def parse_cocotb_results(path: Path) -> dict[str, object]:
    """Parse le xUnit réel de cocotb. Refuse XML vide / malformé."""
    root = ElementTree.parse(path).getroot()
    cases = root.findall(".//testcase")
    if root.tag == "testcase":
        cases = [root]
    if not cases:
        raise ValueError("Le rapport cocotb ne contient aucun testcase")
    failed = sum(any(case.find(tag) is not None for tag in ("failure", "error"))
                 for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {
        "tests": len(cases),
        "passed": len(cases) - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "testcases": [
            {
                "name": case.get("name"),
                "status": ("failed" if any(case.find(tag) is not None
                                           for tag in ("failure", "error"))
                           else "skipped" if case.find("skipped") is not None else "passed"),
            } for case in cases
        ],
    }


def _save(out: Path, report: dict) -> dict:
    (out / "simulation.result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def simulate(d: Design, out: Path, timeout: int = 180) -> dict:
    """Lance un banc de test approuvé, puis valide les résultats xUnit.

    Un exit-code 0 du simulateur seul ne signifie *pas* succès :
    cocotb peut écrire des failures dans XML même si le process se termine à 0.
    """
    out.mkdir(parents=True, exist_ok=True)
    results_xml = out / "simulation_results.xml"
    config_path = out / "simulation.config.json"

    # Jamais de faux succès à cause d'un ancien run.
    for stale in (
        results_xml, config_path, out / "simulation.result.json",
        out / "simulation.stdout.log", out / "simulation.stderr.log",
    ):
        stale.unlink(missing_ok=True)
    report: dict = {
        "task": "simulation", "top": d.top, "status": "not_run",
        "source_fingerprint": fingerprint(d),
        "sources": [str(p) for p in d.sources],
        "suite": TEST_SUITES.get(d.top),
        "results_xml": str(results_xml),
        "tests": 0, "passed": 0, "failed": 0, "skipped": 0,
    }
    if timeout < 1:
        report.update(status="failed", error="timeout doit être >= 1 seconde")
        return _save(out, report)
    if d.top not in TEST_SUITES:
        report.update(status="failed",
                      error=f"Aucun banc cocotb approuvé pour le top {d.top!r}")
        return _save(out, report)
    missing = [t for t in ("verilator", "make", "g++") if shutil.which(t) is None]
    if importlib.util.find_spec("cocotb") is None or importlib.util.find_spec("cocotb_tools") is None:
        missing.append("cocotb (installer avec python -m pip install -e '.[simulation]')")
    if missing:
        report.update(status="missing_tool", error="Dépendances absentes : " + ", ".join(missing))
        return _save(out, report)

    try:
        report["cocotb_version"] = importlib.metadata.version("cocotb")
        version = subprocess.run(["verilator", "--version"], capture_output=True,
                                 text=True, timeout=10, check=True)
        report["verilator_version"] = version.stdout.strip()
    except (subprocess.SubprocessError, OSError, importlib.metadata.PackageNotFoundError) as exc:
        report.update(status="error", error=f"Versions d'outils inaccessibles : {exc}")
        return _save(out, report)

    # Aucun module Python arbitraire ne provient du manifeste utilisateur.
    config_path.write_text(json.dumps({
        "top": d.top,
        "sources": [str(p) for p in d.sources],
        "includes": [str(p) for p in d.includes],
        "defines": list(d.defines),
        "test_module": TEST_SUITES[d.top],
        "build_dir": str(out / "simulation_build"),
        "results_xml": str(results_xml),
        "out_dir": str(out),
    }, indent=2), encoding="utf-8")
    result = run_command(
        [sys.executable, "-m", "rtlprep.sim_worker", str(config_path)],
        "simulation", out, timeout,
    )
    report.update({
        "status": result["status"], "returncode": result["returncode"],
        "elapsed_seconds": result["elapsed_seconds"],
        "argv": result["argv"],
    })
    if "error" in result:
        report["error"] = result["error"]

    if results_xml.is_file():
        try:
            counts = parse_cocotb_results(results_xml)
            report.update(counts)
            if counts["failed"]:
                report["status"] = "failed"
                report["error"] = f"{counts['failed']} test(s) cocotb échoué(s)"
            elif counts["skipped"]:
                report["status"] = "inconclusive"
                report["error"] = f"{counts['skipped']} test(s) cocotb ignoré(s)"
            elif result["status"] == "passed":
                report["status"] = "passed"
        except (ElementTree.ParseError, ValueError, OSError) as exc:
            if report["status"] == "passed":
                report["status"] = "failed"
            report["error"] = f"Résultats xUnit cocotb invalides : {exc}"
    elif report["status"] == "passed":
        report["status"] = "failed"
        report["error"] = "Aucun rapport xUnit produit par cocotb"
    return _save(out, report)
