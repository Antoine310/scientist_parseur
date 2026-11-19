from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Design:
    manifest: Path
    top: str
    sources: tuple[Path, ...]
    includes: tuple[Path, ...]
    defines: tuple[str, ...]


def load_design(filename: str | Path) -> Design:
    path = Path(filename).expanduser().resolve()
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    top = raw.get("top")
    if not isinstance(top, str) or not top or not all(c.isalnum() or c in "_$" for c in top):
        raise ValueError("Le champ 'top' doit etre un identifiant SystemVerilog simple")
    srcs = raw.get("sources")
    if not isinstance(srcs, list) or not srcs or not all(isinstance(x, str) for x in srcs):
        raise ValueError("'sources' doit etre une liste non vide de chemins")

    def paths(values: list[str]) -> tuple[Path, ...]:
        return tuple((path.parent / p).resolve() for p in values)

    sources = paths(srcs)
    for src in sources:
        if not src.is_file():
            raise FileNotFoundError(f"RTL manquant : {src}")
    include_dirs = raw.get("include_dirs", [])
    if not isinstance(include_dirs, list) or not all(isinstance(x, str) for x in include_dirs):
        raise ValueError("'include_dirs' doit etre une liste de chemins")
    includes = paths(include_dirs)
    for inc in includes:
        if not inc.is_dir():
            raise FileNotFoundError(f"Include directory manquant : {inc}")
    defines = raw.get("defines", [])
    if not isinstance(defines, list) or not all(isinstance(x, str) for x in defines):
        raise ValueError("'defines' doit etre une liste de chaines (ex. FOO=1)")
    for define in defines:
        if not define or not all(c.isalnum() or c in "_$=" for c in define):
            raise ValueError(f"Macro invalide : {define}")
    return Design(path, top, sources, includes, tuple(defines))
