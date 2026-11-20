"""Vérification formelle contrôlée avec SBY/Yosys/SMT, preuves et traces.

Deux bancs de preuve revus sont autorisés : compteur et handshake FSM.
Le manifeste ne peut fournir ni commandes Yosys, ni assertions exécutables,
ni fichier .sby. Les configurations sont générées par RTLPrep.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .manifest import Design
from .runner import fingerprint, run_command

PROOF_SUITES = {
    "counter": ("counter_properties.sv", "counter_formal"),
    "handshake_fsm": ("handshake_fsm_properties.sv", "handshake_fsm_formal"),
}
FORMAL_DIR = Path(__file__).resolve().parent / "formal_specs"
VALID_FILENAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def create_sby_config(d: Design, *, task: str, source: Path,
                      properties: Path) -> str:
    """Générer un .sby sans interpréter d'options provenant du RTL."""
    if task not in ("prove", "cover"):
        raise ValueError(f"Mode SBY inconnu : {task}")
    if len(d.sources) != 1 or source != d.sources[0]:
        raise ValueError("Ce banc formel n'accepte qu'un fichier source RTL")
    if not VALID_FILENAME.fullmatch(source.name):
        raise ValueError("Nom du fichier RTL incompatible avec le format .sby")
    if source.name == properties.name:
        raise ValueError("Collision entre fichier RTL et propriétés")
    _, formal_top = PROOF_SUITES[d.top]
    mode = "prove" if task == "prove" else "cover"
    depth = 12 if task == "prove" else 20
    return (
        "[options]\n"
        f"mode {mode}\n"
        f"depth {depth}\n"
        "multiclock on\n"
        "\n[engines]\n"
        "smtbmc z3\n"
        "\n[script]\n"
        f"read -formal -sv {source.name} {properties.name}\n"
        f"prep -top {formal_top}\n"
        "\n[files]\n"
        f"{source}\n"
        f"{properties}\n"
    )


def _persist(out: Path, result: dict) -> dict:
    (out / "formal.result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def _sby_status(path: Path) -> str | None:
    try:
        # sby écrit par exemple "UNKNOWN 4 0" et non seulement "UNKNOWN".
        # Seul le premier champ contient le verdict; la suite code rc/temps.
        tokens = path.read_text(encoding="utf-8").strip().upper().split()
    except OSError:
        return None
    value = tokens[0] if tokens else None
    return value if value in ("PASS", "FAIL", "UNKNOWN", "ERROR", "TIMEOUT") else None


def _classify(process: dict, sby_status: str | None) -> str:
    if process["status"] == "timeout":
        return "timeout"
    if process["status"] != "passed" and sby_status is None:
        return "failed"
    return {
        "PASS": "passed",
        "FAIL": "failed",
        "UNKNOWN": "inconclusive",
        "ERROR": "error",
        "TIMEOUT": "timeout",
    }.get(sby_status, "failed") if not (
        sby_status == "PASS" and process["status"] != "passed"
    ) else "failed"


def formal_verify(d: Design, out: Path, timeout: int = 180) -> dict:
    """Vérifie une propriété et cherche un témoin de non-vacuité.

    Ne confond jamais retour d'exécution 0, preuve par induction réussie,
    et couverture d'un scénario intéressant. Ne recycle pas les résultats.
    """
    out.mkdir(parents=True, exist_ok=True)
    for name in ("formal.result.json", "formal_prove.sby", "formal_cover.sby",
                 "formal_prove.result.json", "formal_cover.result.json",
                 "formal_prove.stdout.log", "formal_prove.stderr.log",
                 "formal_cover.stdout.log", "formal_cover.stderr.log"):
        (out / name).unlink(missing_ok=True)
    for name in ("formal_prove_work", "formal_cover_work"):
        shutil.rmtree(out / name, ignore_errors=True)

    result: dict = {
        "task": "formal", "top": d.top, "status": "not_run",
        "source_fingerprint": fingerprint(d), "proof": None, "cover": None,
        "assumptions": ["reset actif au démarrage"],
        "scope": "propriété d'un banc formel approuvé, pas preuve du CPU complet",
    }
    if timeout < 1:
        result.update(status="failed", error="timeout doit être >= 1 seconde")
        return _persist(out, result)
    if d.top not in PROOF_SUITES:
        result.update(status="failed", error=f"Aucun banc formel approuvé pour le top {d.top!r}")
        return _persist(out, result)
    if len(d.sources) != 1 or d.includes or d.defines:
        result.update(status="failed", error="Banc formel v1 : exactement une source, sans include ni defines")
        return _persist(out, result)
    missing = [tool for tool in ("sby", "yosys", "z3") if not shutil.which(tool)]
    if missing:
        result.update(status="missing_tool", error="Outils absents : " + ", ".join(missing))
        return _persist(out, result)

    properties_name, formal_top = PROOF_SUITES[d.top]
    properties = FORMAL_DIR / properties_name
    source = d.sources[0]
    try:
        result["formal_top"] = formal_top
        result["versions"] = {
            name: subprocess.run([name, "-V" if name == "yosys" else "--version"],
                                 capture_output=True, text=True, timeout=10,
                                 check=False).stdout.strip().splitlines()[:1]
            for name in ("sby", "yosys", "z3")
        }
        for task in ("prove", "cover"):
            config = out / f"formal_{task}.sby"
            config.write_text(create_sby_config(
                d, task=task, source=source, properties=properties
            ), encoding="utf-8")
            work_dir = out / f"formal_{task}_work"
            proc = run_command(
                ["sby", "-f", "-d", str(work_dir), str(config)],
                f"formal_{task}", out, timeout,
            )
            sby_status = _sby_status(work_dir / "status")
            verdict = _classify(proc, sby_status)
            task_result = {
                "status": verdict, "sby_status": sby_status,
                "returncode": proc.get("returncode"),
                "elapsed_seconds": proc.get("elapsed_seconds"),
                "work_dir": str(work_dir),
                "log": str(work_dir / "logfile.txt"),
                "trace_files": [str(path) for path in sorted(work_dir.glob("**/trace*.vcd"))],
            }
            if "error" in proc:
                task_result["error"] = proc["error"]
            result["proof" if task == "prove" else "cover"] = task_result
            if verdict != "passed":
                result["status"] = verdict
                result["error"] = f"SBY {task}: {verdict} (verdict={sby_status!r})"
                break
        else:
            result["status"] = "passed"
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        result.update(status="error", error=f"Exécution SBY impossible : {exc}")
    return _persist(out, result)
