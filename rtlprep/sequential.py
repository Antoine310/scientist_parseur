"""Candidats de transition séquentielle, dérivés de chemins AST slang bornés.

Ne simule pas les NBA, les valeurs, les cycles ni la faisabilité des gardes.
Une ressemblance de reset est un motif syntaxique, pas un classement prouvé.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

SEQUENTIAL_SCHEMA_VERSION = 1
MAX_PATHS_PER_TARGET = 32
MAX_WRITES_PER_PATH = 32


def _asserted_level(guard: Any) -> tuple[str, str] | None:
    """Niveau logique de la branche pour un signal simple / sa négation."""
    if not isinstance(guard, dict) or guard.get("kind") != "if":
        return None
    branch = guard.get("branch")
    cond = guard.get("condition")
    if branch not in ("then", "else") or not isinstance(cond, dict):
        return None
    inversion = False
    if cond.get("kind") == "unary" and cond.get("operator") == "LogicalNot":
        inversion = True
        cond = cond.get("operand")
    if not isinstance(cond, dict) or cond.get("kind") != "signal":
        return None
    signal = cond.get("path")
    if not isinstance(signal, str) or not signal:
        return None
    high = (branch == "then") != inversion
    return signal, "high" if high else "low"


def _event_guard_candidate(guards: Any, events: Any, rhs: Any) -> dict[str, Any] | None:
    """Motif facultatif : événement supplémentaire + garde extérieure + littéral.

    Requiert deux événements *distincts* ; un simple @(posedge clk)
    n'est jamais étiqueté comme reset sur la seule base d'une garde.
    """
    if not isinstance(guards, list) or not guards or not isinstance(events, list):
        return None
    # slang entoure parfois les littéraux par des conversions de taille
    # ou de signe. Garder leur provenance syntaxique sans supposer la
    # valeur (ni la largeur) du résultat après conversion.
    literal = rhs
    conversion_kinds: list[str] = []
    for _ in range(8):
        if not isinstance(literal, dict):
            return None
        if literal.get("kind") != "conversion":
            break
        ast_kind = literal.get("ast_kind")
        if ast_kind not in ("Conversion", "SignedConversion"):
            return None
        conversion_kinds.append(ast_kind)
        literal = literal.get("operand")
    if not isinstance(literal, dict) or literal.get("kind") != "literal":
        return None
    event_signals = {
        item.get("signal") for item in events if isinstance(item, dict)
        and isinstance(item.get("signal"), str)
    }
    if len(event_signals) < 2:
        return None
    assertion = _asserted_level(guards[0])
    if assertion is None:
        return None
    signal, level = assertion
    edge = "PosEdge" if level == "high" else "NegEdge"
    if not any(isinstance(item, dict) and
               item.get("signal") == signal and item.get("edge") == edge
               for item in events):
        return None
    candidate = {
        "signal": signal, "edge": edge, "asserted_level": level,
        "literal_write": literal.get("value"),
        "classification": "reset_like_guard_candidate_not_proof",
    }
    if conversion_kinds:
        candidate["rhs_conversion_kinds"] = conversion_kinds
    return candidate


def build_sequential_candidates(flow: dict[str, Any]) -> dict[str, Any]:
    """Proposer des écritures finales par chemin, avec inconnues explicites."""
    if not isinstance(flow, dict) or flow.get("schema_version") != 1:
        raise ValueError("register_flow v1 requis pour sequential_candidates")
    raw = flow.get("items")
    counts = flow.get("counts")
    if not isinstance(raw, list) or not isinstance(counts, dict):
        raise ValueError("register_flow malformé pour sequential_candidates")
    truncated = counts.get("truncated")
    if type(truncated) is not bool:
        raise ValueError("Troncature register_flow malformée")

    targets = Counter(row.get("target") for row in raw
                      if isinstance(row, dict) and isinstance(row.get("target"), str))
    stats: dict[str, Any] = {
        "captured": len(raw), "complete_targets": 0, "partial_targets": 0,
        "unwritten_paths": 0, "multiple_nba_paths": 0,
        "reset_like_candidate_paths": 0,
        "cross_process_targets": sum(n > 1 for n in targets.values()),
        "truncated": truncated,
    }
    rows: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Enregistrement register_flow non structuré")
        target, process = entry.get("target"), entry.get("process")
        if not isinstance(target, str) or not isinstance(process, str):
            raise ValueError("Cible ou processus register_flow manquant")
        row: dict[str, Any] = {
            "target": target,
            "process": process,
            "source": entry.get("source"),
            "events": entry.get("events") if isinstance(entry.get("events"), list) else [],
            "multiple_processes_same_target": targets[target] > 1,
            "priority_scope": "same_process_and_syntactic_path_only",
            "coverage": "partial",
            "reset_like_detection": "unknown",
            "paths": [],
        }
        if entry.get("coverage") != "syntactic_paths_supported":
            row["reason"] = str(entry.get("reason") or "incomplete_register_flow")[:96]
            rows.append(row)
            stats["partial_targets"] += 1
            continue
        paths = entry.get("paths")
        if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_PATHS_PER_TARGET:
            row["reason"] = "invalid_or_bounded_paths"
            rows.append(row)
            stats["partial_targets"] += 1
            continue
        out: list[dict[str, Any]] = []
        failed = None
        for idx, path in enumerate(paths):
            if not isinstance(path, dict):
                failed = "malformed_path"
                break
            writes, guards = path.get("writes_in_execution_order"), path.get("guards")
            if not isinstance(writes, list) or not isinstance(guards, list):
                failed = "malformed_writes_or_guards"
                break
            if not 0 <= len(writes) <= MAX_WRITES_PER_PATH or (
                type(path.get("write_count")) is not int or
                path["write_count"] != len(writes)
            ):
                failed = "invalid_write_count"
                break
            if any(not isinstance(w, dict) or type(w.get("order")) is not int
                   for w in writes):
                failed = "malformed_write"
                break
            orders = [w["order"] for w in writes]
            # Do not silently select a winner from inconsistent metadata.
            # Orders are local to one syntactic path, not global time.
            if any(order <= 0 for order in orders) or any(
                a >= b for a, b in zip(orders, orders[1:])
            ):
                failed = "non_monotonic_write_order"
                break
            if not writes:
                candidate: dict[str, Any] = {"kind": "unwritten_in_this_process"}
                match = None
            else:
                last = writes[-1]
                rhs = last.get("rhs")
                if isinstance(rhs, dict) and rhs.get("kind") not in ("unknown", "unsupported"):
                    candidate = {
                        "kind": "last_nba_rhs_syntax", "rhs": rhs,
                        "write_order": last["order"],
                        "source": last.get("source"),
                    }
                    match = _event_guard_candidate(guards, row["events"], rhs)
                else:
                    candidate = {
                        "kind": "unknown_rhs", "write_order": last["order"],
                        "source": last.get("source"),
                    }
                    match = None
            out.append({
                "path_index": idx, "guards": guards,
                "write_count": len(writes),
                "local_overwritten_orders": [w["order"] for w in writes[:-1]],
                "transition_candidate": candidate,
                "reset_like_guard_candidate": match,
            })
        if failed:
            row["reason"] = failed
            rows.append(row)
            stats["partial_targets"] += 1
            continue
        row["coverage"] = "syntactic_candidates_supported"
        row["reset_like_detection"] = "candidate_found" if any(
            p["reset_like_guard_candidate"] is not None for p in out
        ) else "none_matched_in_supported_paths"
        row["paths"] = out
        stats["complete_targets"] += 1
        stats["unwritten_paths"] += sum(
            p["transition_candidate"]["kind"] == "unwritten_in_this_process"
            for p in out
        )
        stats["multiple_nba_paths"] += sum(
            p["write_count"] > 1 for p in out
        )
        stats["reset_like_candidate_paths"] += sum(
            p["reset_like_guard_candidate"] is not None for p in out
        )
        rows.append(row)

    return {
        "schema_version": SEQUENTIAL_SCHEMA_VERSION,
        "scope": "supported_always_ff_syntactic_transition_candidates",
        "items": rows,
        "counts": stats,
        "caveat": (
            "Candidats syntaxiques par chemin always_ff, sans preuve de "
            "faisabilite, d'absence de X/Z ni de transition d'etat reelle. "
            "La RHS de la derniere NBA n'est pas une valeur simulee. "
            "Les motifs reset-like croisent un evenement, une garde externe "
            "et une RHS litterale, mais ne prouvent ni un reset asynchrone, "
            "ni sa priorite inter-processus. Les chemins et processus "
            "partiels sont inconnus ; les autres processus ne sont pas ordonnes."
        ),
    }
