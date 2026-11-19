from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .analysis import summarize_ast
from .manifest import Design

TOOL_NAMES = ("slang", "verilator", "yosys", "sby", "eqy", "openroad")


def doctor() -> dict:
    import importlib.util
    return {
        "tools": {name: shutil.which(name) for name in TOOL_NAMES},
        "python_modules": {
            name: importlib.util.find_spec(name) is not None
            for name in ("pyslang", "cocotb", "pytest")
        },
    }


def fingerprint(design: Design) -> str:
    h = hashlib.sha256()
    h.update(design.top.encode())
    for source in design.sources:
        h.update(str(source).encode())
        h.update(source.read_bytes())
    for path in design.includes:
        h.update(str(path).encode())
    for define in design.defines:
        h.update(define.encode())
    return h.hexdigest()


def run_command(cmd: list[str], label: str, out_dir: Path, timeout: int = 120) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    executable = shutil.which(cmd[0])
    result = {
        "task": label, "argv": cmd, "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "missing_tool" if executable is None else "not_run",
        "returncode": None, "elapsed_seconds": 0.0,
    }
    if executable is None:
        result["error"] = f"Outil absent du PATH: {cmd[0]}"
    else:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=False,
            )
            result["elapsed_seconds"] = round(time.monotonic() - start, 3)
            result["returncode"] = proc.returncode
            result["status"] = "passed" if proc.returncode == 0 else "failed"
            (out_dir / f"{label}.stdout.log").write_text(proc.stdout, encoding="utf-8")
            (out_dir / f"{label}.stderr.log").write_text(proc.stderr, encoding="utf-8")
        except subprocess.TimeoutExpired as exc:
            result["elapsed_seconds"] = round(time.monotonic() - start, 3)
            result["status"] = "timeout"
            result["error"] = f"Timeout de {timeout} s"
            if exc.stdout:
                data = exc.stdout if isinstance(exc.stdout, bytes) else exc.stdout.encode()
                (out_dir / f"{label}.stdout.log").write_bytes(data)
            if exc.stderr:
                data = exc.stderr if isinstance(exc.stderr, bytes) else exc.stderr.encode()
                (out_dir / f"{label}.stderr.log").write_bytes(data)
        except OSError as exc:
            result["status"] = "error"
            result["error"] = str(exc)
    (out_dir / f"{label}.result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    return result


def common_verilator_args(d: Design) -> list[str]:
    args = ["--top-module", d.top]
    for inc in d.includes:
        args.append("+incdir+" + str(inc))
    for define in d.defines:
        args.append("+define+" + define)
    args.extend(str(f) for f in d.sources)
    return args


def common_slang_args(d: Design) -> list[str]:
    args = ["--top", d.top]
    for inc in d.includes:
        args.append("-I" + str(inc))
    for define in d.defines:
        args.append("-D" + define)
    args.extend(str(f) for f in d.sources)
    return args


def analyze(d: Design, out: Path, timeout: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ast_path = out / "elaborated_ast.json"
    summary_path = out / "design_summary.json"
    # Ne jamais réutiliser par erreur les artefacts d'une précédente exécution.
    ast_path.unlink(missing_ok=True)
    summary_path.unlink(missing_ok=True)
    cmd = ["slang", "--ast-json", str(ast_path), "--ast-json-source-info", *common_slang_args(d)]
    result = run_command(cmd, "analyze", out, timeout)
    if result["status"] == "passed":
        try:
            raw = json.loads(ast_path.read_text(encoding="utf-8"))
            summary = summarize_ast(raw, expected_top=d.top)
            summary["top"] = d.top
            summary["source_fingerprint"] = fingerprint(d)
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            result["summary"] = str(summary_path)
        except (ValueError, OSError, TypeError) as exc:
            result["status"] = "failed"
            result["error"] = f"AST JSON inexploitable : {exc}"
        # run_command écrit un premier rapport ; le mettre à jour après post-traitement.
        (out / "analyze.result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def lint(d: Design, out: Path, timeout: int) -> dict:
    cmd = ["verilator", "--lint-only", "-Wall", "-Wno-fatal", *common_verilator_args(d)]
    return run_command(cmd, "lint", out, timeout)


def _quote_yosys(text: str) -> str:
    if any(ch in text for ch in '\n\r";'):
        raise ValueError("Chemin ou option incompatible avec Yosys")
    return f'"{text}"'


def synth(d: Design, out: Path, timeout: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    options = [
        "-sv",
        *["-I" + _quote_yosys(str(inc)) for inc in d.includes],
        *["-D" + define for define in d.defines],
    ]
    commands = [
        "read_verilog " + " ".join(options + [_quote_yosys(str(src)) for src in d.sources]),
        f"hierarchy -check -top {d.top}",
        "proc",
        "opt",
        f"synth -top {d.top}",
        "write_json " + _quote_yosys(str(out / "netlist.json")),
    ]
    script_path = out / "synthesis.ys"
    script_path.write_text("\n".join(commands) + "\n", encoding="utf-8")
    result = run_command(["yosys", "-s", str(script_path)], "synth", out, timeout)
    if result["status"] == "passed":
        try:
            raw = json.loads((out / "netlist.json").read_text(encoding="utf-8"))
            selected = raw.get("modules", {}).get(d.top, {})
            if not selected:
                raise ValueError("top absent de netlist.json")
            cells = selected.get("cells", {})
            by_type: dict[str, int] = {}
            for cell in cells.values():
                typ = cell.get("type", "unknown")
                by_type[typ] = by_type.get(typ, 0) + 1
            result["cell_count"] = len(cells)
            result["cells_by_type"] = dict(sorted(by_type.items()))
            (out / "synth_stats.json").write_text(
                json.dumps({"top": d.top, "cell_count": len(cells), "cells_by_type": by_type}, indent=2),
                encoding="utf-8",
            )
        except (OSError, ValueError, TypeError) as exc:
            result["status"] = "failed"
            result["error"] = f"Impossible de lire la netlist: {exc}"
        (out / "synth.result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    return result
