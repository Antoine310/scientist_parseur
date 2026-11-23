"""Résolution d'identité des symboles d'un *même* AST slang élaboré.

Les adresses "addr" / "symbol" sont instables entre exécutions. Elles ne
sont jamais persistées dans les index JSON. Les scopes generate sont
représentés par un chemin qualifié et non aplatis au niveau du module.

Par sécurité, les adresses inconnues ne sont pas résolues à partir du seul
nom lorsqu'une déclaration d'AST possède une adresse. Ce fallback est limité
aux fixtures AST anciennes sans champ addr (tests de compatibilité).
"""
from __future__ import annotations

import re
from typing import Any

SCOPED_NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\[[0-9]+\])?\Z")
DECL_KINDS = frozenset({"Variable", "Net", "Port"})


def declared_path(instance: str, scopes: tuple[str, ...], name: str) -> str:
    return ".".join((instance, *scopes, name))


def generate_scope(node: dict[str, Any]) -> str | None:
    value = node.get("name")
    return value if isinstance(value, str) and SCOPED_NAME.fullmatch(value) else None


def member_name(node: Any) -> str | None:
    """Return a bounded member identifier from slang's semantic member token.

    The JSON representation is 'declaration-address member-name'.  The
    address must not be persisted and a name alone is never a proof that
    the base is a constant or a signal.  Unexpected shapes fail closed.
    """
    if not isinstance(node, dict) or node.get("kind") != "MemberAccess":
        return None
    raw = node.get("member")
    if not isinstance(raw, str) or len(raw) > 192:
        return None
    parts = raw.split(maxsplit=1)
    if (len(parts) != 2 or not parts[0].isdecimal()
            or not SCOPED_NAME.fullmatch(parts[1])):
        return None
    return parts[1]


class SignalResolver:
    """Retrouve le signal indexé par l'adresse sémantique *et* son instance."""

    def __init__(self, ast: dict[str, Any], index: dict[str, Any]) -> None:
        existing: dict[tuple[str, str], str] = {}
        for instance in index["instances"]:
            owner = instance["path"]
            for port in instance["ports"]:
                existing[(owner, declared_path(owner, (), port["name"]))] = port["name"]
        for item in index["signals"]:
            owner = item["instance_path"]
            full_path = item.get("path") or declared_path(owner, (), item["name"])
            existing[(owner, full_path)] = item["name"]

        self._by_id: dict[tuple[str, str], tuple[str, str]] = {}
        self._ambiguous: set[tuple[str, str]] = set()
        self._by_name: dict[tuple[str, str], set[str]] = {}
        self._names_with_ids: set[tuple[str, str]] = set()

        def add_declaration(node: dict[str, Any], owner: str,
                            scopes: tuple[str, ...]) -> None:
            name = node.get("name")
            if not isinstance(name, str) or not name:
                return
            canonical = declared_path(owner, scopes, name)
            if (owner, canonical) not in existing:
                return
            key = (owner, name)
            self._by_name.setdefault(key, set()).add(canonical)
            address = node.get("addr")
            if address is None:
                return
            address_key = (owner, str(address))
            self._names_with_ids.add(key)
            candidate = (name, canonical)
            before = self._by_id.get(address_key)
            if before is not None and before != candidate:
                self._ambiguous.add(address_key)
            else:
                self._by_id[address_key] = candidate

        def visit(members: Any, owner: str | None = None,
                  scopes: tuple[str, ...] = (),
                  scope_safe: bool = True) -> None:
            if not isinstance(members, list):
                return
            for node in members:
                if not isinstance(node, dict):
                    continue
                kind = node.get("kind")
                if kind == "Instance":
                    name = node.get("name")
                    body = node.get("body")
                    if isinstance(name, str) and isinstance(body, dict):
                        child_owner = f"{owner}.{name}" if owner else name
                        visit(body.get("members"), child_owner, (), True)
                    continue
                if kind in ("GenerateBlock", "GenerateBlockArray", "Scope"):
                    if node.get("isUninstantiated") is True:
                        continue
                    if kind == "GenerateBlock":
                        label = generate_scope(node)
                        if label is not None and scope_safe:
                            visit(node.get("members"), owner, (*scopes, label), True)
                        else:
                            visit(node.get("members"), owner, scopes, False)
                    else:
                        # Le conteneur d'array n'est pas une portée nommée
                        # fiable ; les blocs enfants doivent fournir leur nom.
                        visit(node.get("members"), owner, scopes, scope_safe)
                    continue
                if owner and scope_safe and kind in DECL_KINDS:
                    add_declaration(node, owner, scopes)

        visit(ast.get("design", {}).get("members"))

    def resolve(self, instance: str, node: Any) -> str | None:
        if not isinstance(node, dict) or node.get("kind") != "NamedValue":
            return None
        raw = node.get("symbol")
        if not isinstance(raw, str):
            return None
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            return None
        address, name = parts
        key = (instance, address)
        if key in self._ambiguous:
            return None
        entry = self._by_id.get(key)
        if entry is not None:
            declared_name, path = entry
            return path if declared_name == name else None
        # Pas de liaison par nom si l'AST connaît une adresse de déclaration :
        # ceci pourrait raccorder un homonyme dont l'identité est différente.
        if (instance, name) in self._names_with_ids:
            return None
        candidates = self._by_name.get((instance, name), set())
        return next(iter(candidates)) if len(candidates) == 1 else None
