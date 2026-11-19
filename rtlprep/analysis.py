"""Inventaire de la hiérarchie élaborée, à partir du JSON AST de slang.

Cette couche ne déduit ni fan-in/fan-out ni comportement temporel.
Elle refuse les arbres dont le schéma ne correspond pas à la structure attendue.
"""
from __future__ import annotations

from typing import Any


def summarize_ast(ast: dict[str, Any], *, expected_top: str | None = None) -> dict[str, Any]:
    """Résumer les instances et ports d'un AST élaboré.

    expected_top valide le module racine demandé au compilateur.
    Les chemins sont hiérarchiques : une définition instanciée deux fois produit
    deux entrées différentes. Un AST vide/malformé soulève ValueError.
    """
    if not isinstance(ast, dict):
        raise ValueError("AST slang : la racine JSON doit être un objet")
    root = ast.get("design")
    if not isinstance(root, dict) or root.get("kind") != "Root":
        raise ValueError("AST slang : design.kind=Root manquant")
    members = root.get("members")
    if not isinstance(members, list):
        raise ValueError("AST slang : design.members doit être une liste")
    top_nodes = [m for m in members if isinstance(m, dict) and m.get("kind") == "Instance"]
    if not top_nodes:
        raise ValueError("AST slang : aucune instance de premier niveau")
    if expected_top is not None and not any(
        m.get("name") == expected_top or (
            isinstance(m.get("body"), dict) and m["body"].get("name") == expected_top
        ) for m in top_nodes
    ):
        raise ValueError(f"AST slang : top '{expected_top}' absent des instances racines")

    result: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    def walk(obj: Any, parents: tuple[str, ...] = ()) -> None:
        if isinstance(obj, list):
            for x in obj:
                walk(x, parents)
        elif isinstance(obj, dict):
            new_parents = parents
            if obj.get("kind") == "Instance":
                name = obj.get("name")
                body = obj.get("body")
                if not isinstance(name, str) or not name or not isinstance(body, dict):
                    raise ValueError("AST slang : Instance sans nom ou corps valide")
                module = body.get("name")
                children = body.get("members")
                if not isinstance(module, str) or not module or not isinstance(children, list):
                    raise ValueError(f"AST slang : InstanceBody invalide pour '{name}'")
                new_parents = (*parents, name)
                path = ".".join(new_parents)
                if path in seen_paths:
                    raise ValueError(f"AST slang : chemin d'instance dupliqué : {path}")
                seen_paths.add(path)
                ports = []
                for member in children:
                    if isinstance(member, dict) and member.get("kind") == "Port":
                        ports.append({
                            "name": member.get("name"),
                            "direction": member.get("direction"),
                            "type": member.get("type"),
                        })
                result.append({
                    "hierarchy_path": path,
                    "instance": name,
                    "module": module,
                    "ports": ports,
                })
                # Descendre dans les membres élaborés du module, sans reparcourir
                # les métadonnées / connexions pouvant contenir des références.
                walk(children, new_parents)
                return
            # Les instances peuvent être dans des scopes de generate.
            for key, value in obj.items():
                if key in ("addr", "type", "connections", "definition", "internalSymbol"):
                    continue
                walk(value, new_parents)

    walk(members)
    return {
        "format": "slang-elaborated-ast",
        "instances": result,
        "instance_count": len(result),
    }
