"""Equivalence RTL contrôlée avec EQY et rapports de preuve reproductibles.

MVP : uniquement des paires de RTL *revues* du dépôt (compteur et FSM).
Un nom de top identique n'autorise pas des scripts Yosys arbitraries.
EQY prouve des partitions des circuits gold/gate, pas une propriété de sécurité.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .manifest import Design
from .runner import fingerprint, run_command

# Pour éviter d'exécuter du RTL externe non examiné en CI, l'ensemble de
# fichiers admissibles est explicite. Étendre seulement avec tests et revue.
TRUSTED_PAIRS = {
    "counter": ("examples/counter/counter.sv", {
        "examples/counter/counter_refactored.sv",
        "examples/counter/counter_buggy.sv",
    }),
    "handshake_fsm": ("examples/fsm/handshake_fsm.sv", {
        "examples/fsm/handshake_fsm_refactored.sv",
    }),
}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAFE_FILENAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
# Pinned OpenHW CV32E40P release source; exact Git blob object from commit
# b353438ff469c030c89f6804f3b24a2852880e8b. No vendor file copied.
POPCNT_GOLD_BLOB = "c7fe53e810c411a4cef0ab6ae8591b9e54e652f9"
POPCNT_ASSIGN = "  assign result_o = {1'b0, cnt_l4[0]} + {1'b0, cnt_l4[1]};"
POPCNT_REFACTORED = "  assign result_o = {1'b0, cnt_l4[1]} + {1'b0, cnt_l4[0]};"
POPCNT_BUGGY = "  assign result_o = {1'b0, cnt_l4[0]} - {1'b0, cnt_l4[1]};"
POPCNT_GATES = {
    "cv32e40p_popcnt_refactored.sv": POPCNT_REFACTORED,
    "cv32e40p_popcnt_buggy.sv": POPCNT_BUGGY,
}


def git_blob_digest(data: bytes) -> str:
    """Git SHA-1 blob identity, also checked by the pinned upstream workflow."""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()


def popcnt_variant(original: str, *, filename: str) -> str:
    """Deterministic one-line output refactor/mutant; never edit upstream source."""
    if filename not in POPCNT_GATES:
        raise ValueError(f"Variante popcnt non approuvée : {filename}")
    if original.count(POPCNT_ASSIGN) != 1:
        raise ValueError("La ligne originale du résultat popcnt est absente ou ambiguë")
    return original.replace(POPCNT_ASSIGN, POPCNT_GATES[filename], 1)


def _validate_real_popcnt(gold: Design, gate: Design) -> None:
    """Accept only original pinned CPU bytes and precisely generated variants.

    Unlike a name-based allowlist, checking contents prevents arbitrary
    third-party source execution under the trusted CV32E40P top name.
    """
    reference, candidate = gold.sources[0], gate.sources[0]
    if reference.name != "cv32e40p_popcnt.sv" or candidate.name not in POPCNT_GATES:
        raise ValueError("Noms des fichiers CV32E40P popcnt non approuvés")
    if reference.stat().st_size > 100_000 or candidate.stat().st_size > 100_000:
        raise ValueError("Fichier CV32E40P anormalement volumineux")
    ref_bytes = reference.read_bytes()
    if git_blob_digest(ref_bytes) != POPCNT_GOLD_BLOB:
        raise ValueError("Référence popcnt différente du fichier OpenHW épinglé")
    try:
        expected = popcnt_variant(ref_bytes.decode("utf-8"), filename=candidate.name)
    except UnicodeDecodeError as exc:
        raise ValueError("Source OpenHW invalide (UTF-8)") from exc
    if candidate.read_bytes() != expected.encode("utf-8"):
        raise ValueError("Variante popcnt non conforme à la transformation approuvée")



def _trusted_path(path: Path, allowed: str) -> bool:
    # No accepting a same-named file from another directory.
    return path.resolve() == (PROJECT_ROOT / allowed).resolve()


def validate_pair(gold: Design, gate: Design) -> None:
    """Confirme deux circuits d'entraînement autorisés, pas seulement même top."""
    if gold.top != gate.top or gold.top not in (*TRUSTED_PAIRS, "cv32e40p_popcnt"):
        raise ValueError("Comparaison EQY non autorisée : tops incompatibles ou non approuvés")
    if (len(gold.sources) != 1 or len(gate.sources) != 1
            or gold.includes or gate.includes or gold.defines or gate.defines):
        raise ValueError("EQY v1 : une source RTL de chaque côté, sans includes/defines")
    if gold.top == "cv32e40p_popcnt":
        _validate_real_popcnt(gold, gate)
    else:
        expected_gold, allowed_gates = TRUSTED_PAIRS[gold.top]
        if not _trusted_path(gold.sources[0], expected_gold):
            raise ValueError("La référence gold n'est pas un fichier RTL approuvé")
        if not any(_trusted_path(gate.sources[0], x) for x in allowed_gates):
            raise ValueError("La variante gate n'est pas un fichier RTL approuvé")
    for file in (gold.sources[0], gate.sources[0]):
        if not SAFE_FILENAME.fullmatch(file.name):
            raise ValueError("Nom de fichier incompatible avec Yosys/EQY")


def _quote_yosys(path: Path) -> str:
    s = str(path)
    if any(char in s for char in ('"', "\n", "\r", ";", "\\", "\x00")):
        raise ValueError("Chemin non sûr pour le script Yosys/EQY")
    return f'"{s}"'


def make_eqy_config(gold: Design, gate: Design) -> str:
    """Fichier de configuration EQY minimal fondé sur la documentation YosysHQ.

    Le modèle du candidat n'est pas présumé équivalent : le solveur doit
    démontrer les partitions. Les programmes Yosys sont codés en dur.
    """
    validate_pair(gold, gate)
    return (
        "[gold]\n"
        f"read_verilog -formal -sv {_quote_yosys(gold.sources[0])}\n"
        f"prep -top {gold.top}\n"
        "\n[gate]\n"
        f"read_verilog -formal -sv {_quote_yosys(gate.sources[0])}\n"
        f"prep -top {gate.top}\n"
        "\n[strategy induction]\n"
        "use sby\n"
        "engine smtbmc z3\n"
        "depth 12\n"
    )


def _save(out: Path, report: dict[str, Any]) -> dict[str, Any]:
    (out / "equivalence.result.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def read_eqy_verdict(work: Path) -> str | None:
    """EQY crée un marqueur PASS/FAIL dans le répertoire des résultats."""
    has_pass = (work / "PASS").is_file()
    has_fail = (work / "FAIL").is_file()
    if has_pass and has_fail:
        return "CONFLICT"
    return "PASS" if has_pass else "FAIL" if has_fail else None


def _partition_statuses(work: Path) -> list[dict[str, str]]:
    statuses = []
    # EQY/strategies/<partition>/<strategy>/status: "PASS ..." etc.
    for file in sorted((work / "strategies").glob("**/status")):
        try:
            tokens = file.read_text(encoding="utf-8").strip().upper().split()
        except OSError:
            continue
        if tokens:
            statuses.append({
                "path": str(file.relative_to(work)),
                "verdict": tokens[0],
            })
    return statuses


def equivalence_check(gold: Design, gate: Design, out: Path,
                      timeout: int = 180) -> dict[str, Any]:
    """Compare deux versions avec EQY, en refusant les faux succès et faux FAIL."""
    out.mkdir(parents=True, exist_ok=True)
    work = out / "eqy_work"
    for filename in ("equivalence.eqy", "equivalence.result.json",
                     "equivalence.stdout.log", "equivalence.stderr.log",
                     "equivalence.result.json"):
        (out / filename).unlink(missing_ok=True)
    shutil.rmtree(work, ignore_errors=True)

    report: dict[str, Any] = {
        "task": "equivalence", "status": "not_run",
        "top_gold": gold.top, "top_gate": gate.top,
        "gold_fingerprint": fingerprint(gold),
        "gate_fingerprint": fingerprint(gate),
        "gold_source": str(gold.sources[0]),
        "gate_source": str(gate.sources[0]),
        "equivalent": None,
        "eqy_verdict": None,
        "partition_count": 0,
        "partition_statuses": [],
        "trace_files": [],
        "work_dir": str(work),
        "scope": "équivalence RTL de deux variantes approuvées sous le modèle Yosys/EQY",
    }
    if timeout < 1:
        report.update(status="failed", error="timeout doit être >= 1 seconde")
        return _save(out, report)
    try:
        cfg = make_eqy_config(gold, gate)
    except ValueError as exc:
        report.update(status="failed", error=str(exc))
        return _save(out, report)

    missing = [tool for tool in ("eqy", "yosys", "sby", "z3")
               if shutil.which(tool) is None]
    if missing:
        report.update(status="missing_tool",
                      error="Outils absents : " + ", ".join(missing))
        return _save(out, report)

    config_path = out / "equivalence.eqy"
    config_path.write_text(cfg, encoding="utf-8")
    try:
        report["versions"] = {
            name: subprocess.run(
                [name, "-V" if name == "yosys" else "--version"],
                capture_output=True, text=True, timeout=10, check=False
            ).stdout.strip().splitlines()[:1]
            for name in ("eqy", "yosys", "sby", "z3")
        }
        process = run_command(
            ["eqy", "-f", "-d", str(work), str(config_path)],
            "equivalence", out, timeout,
        )
        report.update(
            returncode=process.get("returncode"),
            elapsed_seconds=process.get("elapsed_seconds"),
            eqy_verdict=read_eqy_verdict(work),
        )
        report["partition_statuses"] = _partition_statuses(work)
        partition_path = work / "partition.list"
        if partition_path.is_file():
            report["partition_count"] = len(
                [line for line in partition_path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
            )
        traces = sorted({str(p) for p in work.rglob("trace*.vcd")})
        report["trace_files"] = traces
        if "error" in process:
            report["process_error"] = process["error"]

        if process["status"] == "timeout":
            report.update(status="timeout", error="EQY a dépassé la durée maximale")
        elif (process["status"] == "passed" and report["eqy_verdict"] == "PASS"
              and report["partition_count"] > 0):
            report.update(status="passed", equivalent=True)
        elif report["eqy_verdict"] == "FAIL" and any(
            x["verdict"] == "FAIL" for x in report["partition_statuses"]
        ) and traces:
            report.update(status="failed", equivalent=False,
                          error="EQY a trouvé une partition non équivalente (trace VCD conservée)")
        elif report["eqy_verdict"] == "FAIL" and report["partition_count"]:
            report.update(status="inconclusive", error=(
                "EQY n'a pas prouvé l'équivalence. Absence de contre-exemple "
                "vérifié : ne pas conclure à une différence fonctionnelle."
            ))
        else:
            report.update(status="error", error=(
                "EQY n'a pas produit de preuve exploitable : "
                f"processus={process['status']}, verdict={report['eqy_verdict']!r}, "
                f"partitions={report['partition_count']}"
            ))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        report.update(status="error", error=f"Erreur pendant EQY : {exc}")
    return _save(out, report)
