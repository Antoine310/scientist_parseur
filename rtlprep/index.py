"""Index RTL versionné dérivé d'un AST élaboré par slang.

Les relations de dépendance, connexions de ports et informations temporelles
NE sont PAS inférées. Les références source proviennent seulement de slang.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis import summarize_ast
from .symbols import declared_path, generate_scope

SCHEMA_VERSION = 1
SYMBOL_KINDS = frozenset({"Variable", "Net"})


def source_location(node: dict[str, Any]) -> dict[str, Any] | None:
    """Garder uniquement les données source rapportées par slang, sans invention."""
    filename, line, column = (node.get(k) for k in ("source_file", "source_line", "source_column"))
    if not isinstance(filename, str) or not filename:
        return None
    return {"file": filename,
            "line": line if isinstance(line, int) and line > 0 else None,
            "column": column if isinstance(column, int) and column > 0 else None}


def _port(node: dict[str, Any]) -> dict[str, Any]:
    return {"name": node["name"], "direction": node.get("direction"),
            "type": node.get("type"), "source": source_location(node)}


def build_index(ast: dict[str, Any], *, expected_top: str) -> dict[str, Any]:
    """Construire l'index à partir des membres élaborés de chaque instance.

    Valide l'AST via summarize_ast et n'utilise jamais des recherches regex sur RTL.
    Les signaux recensés sont les Variable/Net du module et des blocs
    generate actifs dotés d'un nom de portée non ambigu. Les chemins générés
    sont qualifiés sans changer les chemins historiques des signaux directs.
    """
    validated = summarize_ast(ast, expected_top=expected_top)
    by_path = {item["hierarchy_path"]: item for item in validated["instances"]}
    instances: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    modules: dict[str, dict[str, Any]] = {}

    def traverse(members: list[Any], parents: tuple[str, ...] = (),
                 scopes: tuple[str, ...] = (),
                 scoped_safe: bool = True) -> None:
        for node in members:
            if not isinstance(node, dict):
                continue
            if node.get("kind") == "Instance":
                body = node["body"]
                path_parts = (*parents, node["name"])
                path = ".".join(path_parts)
                if path not in by_path:
                    raise ValueError(f"Instance non validée : {path}")
                module_name = body["name"]
                body_members = body["members"]
                ports = [_port(child) for child in body_members
                         if isinstance(child, dict) and child.get("kind") == "Port"
                         and isinstance(child.get("name"), str)]
                instance = {
                    "path": path, "name": node["name"], "module": module_name,
                    "parent": ".".join(parents) or None,
                    "source": source_location(node),
                    "definition_source": source_location(body),
                    "ports": ports,
                }
                instances.append(instance)
                grouped = modules.setdefault(module_name, {"name": module_name, "instance_paths": []})
                grouped["instance_paths"].append(path)
                for child in body_members:
                    if not isinstance(child, dict) or child.get("kind") not in SYMBOL_KINDS:
                        continue
                    if not isinstance(child.get("name"), str) or not child["name"]:
                        continue
                    signals.append({
                        "instance_path": path, "name": child["name"],
                        "kind": child["kind"], "type": child.get("type"),
                        "source": source_location(child),
                    })
                traverse(body_members, path_parts)
            elif node.get("kind") in ("GenerateBlock", "GenerateBlockArray", "Scope"):
                if node.get("isUninstantiated") is True:
                    continue
                nested = node.get("members")
                if not isinstance(nested, list):
                    continue
                if node["kind"] == "GenerateBlock":
                    label = generate_scope(node)
                    if label is not None and scoped_safe:
                        traverse(nested, parents, (*scopes, label), True)
                    else:
                        traverse(nested, parents, scopes, False)
                else:
                    traverse(nested, parents, scopes, scoped_safe)
            elif (node.get("kind") in SYMBOL_KINDS and parents and
                  scopes and scoped_safe and
                  isinstance(node.get("name"), str) and node["name"]):
                # Une déclaration de generate appartient à l'instance
                # englobante, sans prétendre qu'il existe une instance
                # RTL "genblk". Les chemins qualifiés évitent les collisions.
                owner = ".".join(parents)
                signals.append({
                    "instance_path": owner, "name": node["name"],
                    "path": declared_path(owner, scopes, node["name"]),
                    "scope": ".".join(scopes),
                    "kind": node["kind"], "type": node.get("type"),
                    "source": source_location(node),
                })

    traverse(ast["design"]["members"])
    if len(instances) != validated["instance_count"]:
        raise ValueError("Index incomplet : une instance n'a pas été indexée")
    return {
        "schema_version": SCHEMA_VERSION,
        "backend": "slang-ast-json",
        "top": expected_top,
        "modules": sorted(modules.values(), key=lambda x: x["name"]),
        "instances": instances,
        "signals": signals,
        "counts": {"modules": len(modules), "instances": len(instances), "signals": len(signals)},
        "limitations": [
            "Aucune dépendance fan-in/fan-out calculée",
            "Variable/Net directs et blocs generate actifs nommés seulement ; "
            "les scopes non nommés et arrays complexes restent non garantis",
            "Sources renseignées uniquement si slang fournit source_file/line/column",
            "Les spécialisations paramétrées d'un même module sont regroupées par nom",
        ],
    }


def list_modules(index: dict[str, Any]) -> list[str]:
    return sorted(m["name"] for m in index["modules"])


def get_module_summary(index: dict[str, Any], name: str) -> dict[str, Any]:
    for module in index["modules"]:
        if module["name"] == name:
            return {**module, "instances": [x for x in index["instances"] if x["module"] == name]}
    raise KeyError(f"Module introuvable : {name}")


def get_instance_tree(index: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"path": x["path"], "module": x["module"], "parent": x["parent"]}
            for x in index["instances"]]


def get_instance(index: dict[str, Any], path: str) -> dict[str, Any]:
    for item in index["instances"]:
        if item["path"] == path:
            return item
    raise KeyError(f"Instance introuvable : {path}")


def get_signal_info(index: dict[str, Any], instance_path: str, name: str) -> dict[str, Any]:
    instance = get_instance(index, instance_path)
    # Les clients peuvent interroger "genblk1.reg" sur le même chemin
    # d'instance. Un nom non qualifié ne doit jamais faire croire qu'un
    # registre généré existe directement au niveau du module.
    declarations = [
        x for x in index["signals"]
        if x["instance_path"] == instance_path and (
            (x.get("path") or f"{instance_path}.{x['name']}") ==
            f"{instance_path}.{name}"
        )
    ]
    ports = [x for x in instance["ports"] if x["name"] == name]
    if not declarations and not ports:
        raise KeyError(f"Signal introuvable : {instance_path}.{name}")
    return {"instance_path": instance_path, "name": name,
            "declarations": declarations, "ports": ports}


def get_source_context(sources: tuple[Path, ...], filename: str | Path,
                       line: int, radius: int = 3) -> dict[str, Any]:
    """Afficher un extrait de l'un des fichiers expressément déclarés au manifeste.

    Aucun accès arbitraire à un chemin mentionné dans un AST ou un index tiers.
    """
    if line < 1 or radius < 0 or radius > 30:
        raise ValueError("Ligne >= 1 et rayon entre 0 et 30 requis")
    requested = Path(filename)
    allowed = tuple(x.resolve() for x in sources)
    matches = [x for x in allowed if requested == x or requested == Path(x.name)]
    if len(matches) != 1:
        raise ValueError("Le fichier doit correspondre sans ambiguïté à une source du manifeste")
    source = matches[0]
    lines = source.read_text(encoding="utf-8").splitlines()
    if line > len(lines):
        raise ValueError(f"Ligne {line} inexistante dans {source} ({len(lines)} lignes)")
    begin, end = max(1, line - radius), min(len(lines), line + radius)
    return {"file": str(source), "selected_line": line,
            "lines": [{"line": number, "text": lines[number-1]}
                      for number in range(begin, end + 1)]}
