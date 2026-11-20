from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import load_design
from .runner import analyze, doctor, fingerprint, lint, synth, index_design, dependency_design
from .dependencies import trace_dependencies
from .simulation import simulate
from .formal import formal_verify
from .index import (get_instance, get_instance_tree, get_module_summary,
                    get_signal_info, get_source_context, list_modules)


def main() -> int:
    p = argparse.ArgumentParser(prog="rtlprep", description="Outils RTL locaux, sans cle API")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="afficher les outils et paquets disponibles")
    for name in ("analyze", "lint", "synth", "all", "index", "deps", "simulate", "formal"):
        s = sub.add_parser(name)
        s.add_argument("manifest", help="chemin vers design.json")
        s.add_argument("--out", default="reports", help="dossier de sortie")
        s.add_argument("--timeout", type=int, default=120, help="timeout par outil en secondes")
    q = sub.add_parser("query", help="interroger un rtl_index.json déjà généré")
    q.add_argument("index_file")
    qsub = q.add_subparsers(dest="query_type", required=True)
    qsub.add_parser("modules")
    qsub.add_parser("tree")
    qm = qsub.add_parser("module")
    qm.add_argument("name")
    qi = qsub.add_parser("instance")
    qi.add_argument("path")
    qs = qsub.add_parser("signal")
    qs.add_argument("path")
    qs.add_argument("name")
    source = sub.add_parser("source", help="extrait de code d'un fichier du manifeste")
    source.add_argument("manifest")
    source.add_argument("filename")
    source.add_argument("--line", type=int, required=True)
    source.add_argument("--radius", type=int, default=3)
    trace = sub.add_parser("trace", help="fan-in / fan-out à partir du graphe")
    trace.add_argument("graph_file", help="rtl_dependencies.json")
    trace.add_argument("direction", choices=("fanin", "fanout"))
    trace.add_argument("node", help="signal au format chemin_instance.signal")
    trace.add_argument("--depth", type=int, default=3)
    trace.add_argument("--max-edges", type=int, default=200)
    args = p.parse_args()
    if args.cmd == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        return 0
    try:
        if args.cmd == "trace":
            graph = json.loads(Path(args.graph_file).read_text(encoding="utf-8"))
            result = trace_dependencies(graph, args.node, args.direction,
                                        max_depth=args.depth, max_edges=args.max_edges)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "query":
            data = json.loads(Path(args.index_file).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("Version d'index non prise en charge (attendue : 1)")
            operations = {
                "modules": lambda: list_modules(data),
                "tree": lambda: get_instance_tree(data),
                "module": lambda: get_module_summary(data, args.name),
                "instance": lambda: get_instance(data, args.path),
                "signal": lambda: get_signal_info(data, args.path, args.name),
            }
            print(json.dumps(operations[args.query_type](), ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "source":
            design = load_design(args.manifest)
            info = get_source_context(design.sources, args.filename, args.line, args.radius)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0
        d = load_design(args.manifest)
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / "manifest_snapshot.json").write_text(json.dumps({
            "top": d.top, "sources": [str(x) for x in d.sources],
            "include_dirs": [str(x) for x in d.includes],
            "defines": d.defines, "fingerprint": fingerprint(d),
        }, indent=2), encoding="utf-8")
        tasks = {"analyze": analyze, "lint": lint, "synth": synth, "index": index_design, "deps": dependency_design, "simulate": simulate, "formal": formal_verify}
        keys = ["analyze", "lint", "synth"] if args.cmd == "all" else [args.cmd]
        statuses = []
        for key in keys:
            result = tasks[key](d, out, args.timeout)
            statuses.append(result["status"])
            print(f"[{key}] {result['status']}")
            if result.get("error"):
                print(f"  {result['error']}")
            if key == "formal":
                proof = result.get("proof") or {}
                cover = result.get("cover") or {}
                print(f"  preuve : {proof.get('status', 'non exécutée')}")
                print(f"  témoin : {cover.get('status', 'non exécuté')}")
                for filename in proof.get("trace_files", []):
                    print(f"  contre-exemple : {filename}")
            if key == "simulate":
                print(f"  tests : {result.get('tests', 0)} ; réussis : {result.get('passed', 0)} ; échecs : {result.get('failed', 0)}")
                print(f"  xUnit : {result.get('results_xml')}")
            if result.get("dependencies"):
                print(f"  graphe : {result['dependencies']}")
                print(f"  arêtes : {result['edges']} ; avertissements : {result['graph_warnings']}")
            if result.get("index"):
                print(f"  index : {result['index']}")
            if result.get("summary"):
                print(f"  resume : {result['summary']}")
            if result.get("cell_count") is not None:
                print(f"  cellules : {result['cell_count']}")
        print(f"Rapports : {out}")
        return 0 if all(x == "passed" for x in statuses) else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(2, f"Erreur : {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
