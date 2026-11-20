"""Processus enfant : compiler le RTL et invoquer le runner cocotb officiel.

Appelé uniquement par rtlprep.simulation via une config locale générée par
RTLPrep et une liste blanche de bancs de test. Le processus parent gère
timeouts et rapports (y compris le XML lorsqu'un test cocotb échoue).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .simulation import TEST_SUITES


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python -m rtlprep.sim_worker <simulation.config.json>")
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    top = config["top"]
    if config["test_module"] != TEST_SUITES.get(top):
        raise ValueError("Le banc de test demandé n'est pas approuvé pour ce top")

    # Import local : l'analyse structurale et les tests unitaires restent
    # utilisables sans installer cocotb.
    from cocotb_tools.runner import get_runner

    runner = get_runner("verilator")
    defines = dict(item.split("=", 1) if "=" in item else (item, "1")
                   for item in config["defines"])
    runner.build(
        sources=[Path(src) for src in config["sources"]],
        includes=[Path(inc) for inc in config["includes"]],
        defines=defines,
        hdl_toplevel=top,
        build_dir=Path(config["build_dir"]),
        build_args=["--timing", "-Wno-fatal"],
        timescale=("1ns", "1ps"),
        always=True,
        clean=True,
    )
    runner.test(
        hdl_toplevel=top,
        test_module=config["test_module"],
        build_dir=Path(config["build_dir"]),
        test_dir=Path(config["out_dir"]),
        results_xml=str(config["results_xml"]),
        timescale=("1ns", "1ps"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
