"""Import strict, déterministe et sans exécution de filelists SystemVerilog.

Seuls les chemins sources, les includes, les defines et les filelists imbriquées
sont interprétés. Aucun shell, commande externe, glob, variable d'environnement
ou option EDA arbitraire n'est évalué. En cas d'ambiguïté, arrêter l'import.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

from .manifest import load_design

MAX_LISTS = 128
MAX_DEPTH = 16
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_SOURCES = 5000
MAX_INCLUDES = 1000
MAX_DEFINES = 1000
MAX_TOKENS = 100000
SOURCE_SUFFIXES = frozenset({".v", ".sv"})
MACRO_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:=[A-Za-z0-9_$]*)?\Z")
TOP_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")


class FilelistError(ValueError):
    """Filelist non prise en charge ; refus sans manifeste partiel."""


def _safe_location(path: Path, root: Path, kind: str, *, directory: bool) -> Path:
    candidate = path.expanduser().resolve()
    if not candidate.is_relative_to(root):
        raise FilelistError(f"{kind} sort de --root : {path}")
    if directory and not candidate.is_dir():
        raise FilelistError(f"{kind} inexistant ou non-dossier : {path}")
    if not directory and not candidate.is_file():
        raise FilelistError(f"{kind} inexistant ou non-fichier : {path}")
    return candidate


def _comment_removed(line: str) -> str:
    """Enlever # et // hors chaînes citées ; aucun traitement de commentaires SV."""
    quote: str | None = None
    escaped = False
    for i, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "#" or (char == "/" and line[i:i + 2] == "//"):
            return line[:i]
    return line


def _logical_lines(raw: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    buffer = ""
    first = 1
    for index, physical in enumerate(raw.splitlines(), 1):
        if not buffer:
            first = index
        fragment = physical.rstrip()
        if fragment.endswith("\\"):
            buffer += fragment[:-1] + " "
        else:
            lines.append((first, buffer + fragment))
            buffer = ""
    if buffer:
        raise FilelistError("Continuation '\\' sans ligne suivante")
    return lines


def _split_tokens(text: str, origin: str) -> list[str]:
    tokens: list[str] = []
    for line_no, line in _logical_lines(text):
        clean = _comment_removed(line)
        try:
            parts = shlex.split(clean, posix=True, comments=False)
        except ValueError as exc:
            raise FilelistError(f"{origin}:{line_no}: quoting invalide : {exc}") from exc
        tokens.extend(parts)
        if len(tokens) > MAX_TOKENS:
            raise FilelistError("Filelist trop volumineuse (tokens)")
    return tokens


def _reject_expansion(value: str, context: str) -> None:
    if not value or "\0" in value or "$" in value or chr(96) in value:
        raise FilelistError(
            f"{context}: chemin vide ou expansion de shell non prise en charge : {value!r}"
        )
    if any(c in value for c in ("*", "?", "[", "]", "\r", "\n")):
        raise FilelistError(f"{context}: glob/variable non pris en charge : {value!r}")


def _macro(value: str) -> str:
    if not MACRO_RE.fullmatch(value):
        raise FilelistError(f"Macro non prise en charge : {value!r}")
    return value


def parse_filelist(filelist: str | Path, *, root: str | Path,
                   top: str) -> dict[str, Any]:
    """Construire un manifeste v1 en mémoire ; aucun fichier créé ici.

    Tous les chemins relatifs (y compris -f/-F) sont relatifs au fichier .f
    qui les contient, et tous les chemins résolus restent sous --root.
    Les fichiers sont conservés dans l'ordre d'apparition du filelist,
    notamment les packages avant leurs consommateurs.
    """
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise FilelistError(f"Racine de projet inexistante : {root}")
    if not TOP_RE.fullmatch(top):
        raise FilelistError("Top attendu : identifiant SystemVerilog simple")
    start = _safe_location(Path(filelist), base, "Filelist", directory=False)
    sources: list[Path] = []
    includes: list[Path] = []
    defines: list[str] = []
    lists: list[dict[str, str]] = []
    seen_sources: set[Path] = set()
    seen_includes: set[Path] = set()
    seen_defines: set[str] = set()
    active: list[Path] = []
    bytes_read = 0
    tokens_seen = 0

    def add_source(value: str, parent: Path) -> None:
        _reject_expansion(value, "Source")
        path = _safe_location(parent / value, base, "Source RTL", directory=False)
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            raise FilelistError(
                f"Extension source non prise en charge ({path.suffix}) : {path.name}"
            )
        if path not in seen_sources:
            if len(sources) >= MAX_SOURCES:
                raise FilelistError("Trop de fichiers sources")
            seen_sources.add(path)
            sources.append(path)

    def add_include(value: str, parent: Path) -> None:
        _reject_expansion(value, "Include")
        path = _safe_location(parent / value, base, "Répertoire include", directory=True)
        if path not in seen_includes:
            if len(includes) >= MAX_INCLUDES:
                raise FilelistError("Trop de répertoires include")
            seen_includes.add(path)
            includes.append(path)

    def add_define(value: str) -> None:
        macro = _macro(value)
        if macro not in seen_defines:
            if len(defines) >= MAX_DEFINES:
                raise FilelistError("Trop de macros")
            seen_defines.add(macro)
            defines.append(macro)

    def parse(path: Path) -> None:
        nonlocal bytes_read, tokens_seen
        if path in active:
            chain = " -> ".join(p.relative_to(base).as_posix() for p in (*active, path))
            raise FilelistError(f"Boucle de filelists : {chain}")
        if len(active) >= MAX_DEPTH or len(lists) >= MAX_LISTS:
            raise FilelistError("Profondeur/nombre de filelists dépassé")
        size = path.stat().st_size
        bytes_read += size
        if size > MAX_FILE_BYTES or bytes_read > MAX_TOTAL_BYTES:
            raise FilelistError("Filelist trop volumineuse (octets)")
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise FilelistError(f"Filelist non UTF-8 : {path}") from exc
        tokens = _split_tokens(raw, str(path.relative_to(base)))
        tokens_seen += len(tokens)
        if tokens_seen > MAX_TOKENS:
            raise FilelistError("Trop de tokens de filelists")
        lists.append({
            "path": path.relative_to(base).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        active.append(path)
        try:
            i = 0
            while i < len(tokens):
                token = tokens[i]
                i += 1
                parent = path.parent
                if token in ("-f", "-F", "-I", "-D"):
                    if i >= len(tokens):
                        raise FilelistError(f"{path.name}: argument manquant après {token}")
                    value = tokens[i]
                    i += 1
                    if token in ("-f", "-F"):
                        _reject_expansion(value, "Filelist imbriquée")
                        nested = _safe_location(parent / value, base, "Filelist imbriquée",
                                                directory=False)
                        parse(nested)
                    elif token == "-I":
                        add_include(value, parent)
                    else:
                        add_define(value)
                elif token.startswith("-f") and len(token) > 2:
                    value = token[2:]
                    _reject_expansion(value, "Filelist imbriquée")
                    parse(_safe_location(parent / value, base, "Filelist imbriquée",
                                         directory=False))
                elif token.startswith("-F") and len(token) > 2:
                    value = token[2:]
                    _reject_expansion(value, "Filelist imbriquée")
                    parse(_safe_location(parent / value, base, "Filelist imbriquée",
                                         directory=False))
                elif token.startswith("-I") and len(token) > 2:
                    add_include(token[2:], parent)
                elif token.startswith("-D") and len(token) > 2:
                    add_define(token[2:])
                elif token.startswith("+incdir+"):
                    values = token[len("+incdir+"):].split("+")
                    if any(not x for x in values):
                        raise FilelistError("Entrée +incdir+ vide")
                    for value in values:
                        add_include(value, parent)
                elif token.startswith("+define+"):
                    values = token[len("+define+"):].split("+")
                    if any(not x for x in values):
                        raise FilelistError("Entrée +define+ vide")
                    for value in values:
                        add_define(value)
                elif token.startswith(("-", "+", "@")):
                    raise FilelistError(f"{path.relative_to(base)}: option non prise en charge : {token}")
                else:
                    add_source(token, parent)
        finally:
            active.pop()

    parse(start)
    if not sources:
        raise FilelistError("Aucune source .sv/.v dans le filelist")
    return {
        "top": top,
        "_resolved_sources": sources,
        "_resolved_includes": includes,
        "_defines": defines,
        "_import": {
            "schema_version": 1,
            "source_root": str(base),
            "entry_filelist": start.relative_to(base).as_posix(),
            "filelists": lists,
            "scope": "explicit_filelist_entries_only_no_elaboration_or_dependency_resolution",
            "interpretation": (
                "Ordre de compilation conservé ; aucune inférence de top/packages, "
                "aucun glob ni substitution de variable."
            ),
        },
    }


def write_manifest(filelist: str | Path, *, root: str | Path, top: str,
                   output: str | Path, overwrite: bool = False) -> dict[str, Any]:
    """Écrire atomiquement un manifeste compatible avec load_design, puis le valider."""
    parsed = parse_filelist(filelist, root=root, top=top)
    target = Path(output).expanduser().resolve()
    reserved = set(parsed["_resolved_sources"])
    reserved.update(Path(root).expanduser().resolve() / row["path"]
                    for row in parsed["_import"]["filelists"])
    if target in reserved:
        raise FilelistError("Le manifeste ne peut remplacer une source ou un filelist")
    if target.exists() and not overwrite:
        raise FilelistError(f"Fichier de sortie présent ; ajouter --force : {target}")
    if target.exists() and not target.is_file():
        raise FilelistError("Sortie existante non régulière")
    manifest = {
        "top": parsed["top"],
        "sources": [os.path.relpath(p, target.parent) for p in parsed["_resolved_sources"]],
        "include_dirs": [os.path.relpath(p, target.parent) for p in parsed["_resolved_includes"]],
        "defines": parsed["_defines"],
        "filelist_import": parsed["_import"],
    }
    # Validate paths and parser rules *before* touching the requested destination.
    if not all(p.is_file() for p in parsed["_resolved_sources"]):
        raise FilelistError("Une source a disparu pendant l'import")
    target.parent.mkdir(parents=True, exist_ok=True)
    from tempfile import NamedTemporaryFile
    staging: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                prefix=".rtlprep-filelist-", suffix=".json",
                                delete=False) as temporary:
            staging = Path(temporary.name)
            json.dump(manifest, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
        load_design(staging)
        if target.exists() and not overwrite:
            raise FilelistError(f"Fichier de sortie créé entre temps : {target}")
        staging.replace(target)
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)
    return {
        "manifest": str(target), "top": top,
        "sources_count": len(manifest["sources"]),
        "include_dirs_count": len(manifest["include_dirs"]),
        "defines_count": len(manifest["defines"]),
        "filelists_count": len(parsed["_import"]["filelists"]),
        "scope": parsed["_import"]["scope"],
    }
