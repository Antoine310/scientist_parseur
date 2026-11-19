"""Inventaire d'instances depuis le JSON AST elabore de slang.

Ce n'est pas une analyse complete de fan-in/fan-out.
"""
from __future__ import annotations

from typing import Any


def summarize_ast(ast: dict[str, Any]) -> dict[str, Any]:
    roots = ast.get("design", ast)
    result: list[dict[str, Any]] = []

    def walk(obj: Any, parents: tuple[str, ...] = ()) -> None:
        if isinstance(obj, list):
            for x in obj:
                walk(x, parents)
        elif isinstance(obj, dict):
            new_parents = parents
            if obj.get("kind") == "Instance":
                body = obj.get("body") if isinstance(obj.get("body"), dict) else {}
                name = str(obj.get("name", "<anonymous>"))
                module = str(body.get("name", "<unknown>"))
                new_parents = (*parents, name)
                ports = []
                for member in body.get("members", []):
                    if isinstance(member, dict) and member.get("kind") == "Port":
                        ports.append({
                            "name": member.get("name"),
                            "direction": member.get("direction"),
                            "type": member.get("type"),
                        })
                result.append({
                    "hierarchy_path": ".".join(new_parents),
                    "instance": name,
                    "module": module,
                    "ports": ports,
                })
            for k, v in obj.items():
                if k in ("addr", "type"):
                    continue
                walk(v, new_parents)

    walk(roots)
    return {"format": "slang-elaborated-ast", "instances": result, "instance_count": len(result)}
