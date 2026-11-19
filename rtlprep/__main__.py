from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import load_design
from .runner import analyze, doctor, fingerprint, lint, synth


def main() -> int:
    p = argparse.ArgumentParser(prog="rtlprep", description="Outils RTL locaux, sans cle API")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="afficher les outils et paquets disponibles")
    for name in ("analyze", "lint", "synth", "all"):
        s = sub.add_parser(name)
        s.add_argument("manifest", help="chemin vers design.json")
        s.add_argument("--out", default="reports", help="dossier de sortie")
        s.add_argument("--timeout", type=int, default=120, help="timeout par outil en secondes")
    args = p.parse_args()
    if args.cmd == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        return 0
    try:
        d = load_design(args.manifest)
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / "manifest_snapshot.json").write_text(json.dumps({
            "top": d.top, "sources": [str(x) for x in d.sources],
            "include_dirs": [str(x) for x in d.includes],
            "defines": d.defines, "fingerprint": fingerprint(d),
        }, indent=2), encoding="utf-8")
        tasks = {"analyze": analyze, "lint": lint, "synth": synth}
        keys = list(tasks) if args.cmd == "all" else [args.cmd]
        statuses = []
        for key in keys:
            result = tasks[key](d, out, args.timeout)
            statuses.append(result["status"])
            print(f"[{key}] {result['status']}")
            if result.get("error"):
                print(f"  {result['error']}")
            if result.get("summary"):
                print(f"  resume : {result['summary']}")
            if result.get("cell_count") is not None:
                print(f"  cellules : {result['cell_count']}")
        print(f"Rapports : {out}")
        return 0 if all(x == "passed" for x in statuses) else 2
    except (OSError, ValueError) as exc:
        p.exit(2, f"Erreur : {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
