"""Regression for fresh real-RTL analyzer inventories."""
import pytest

from rtlprep.analysis_budgets import ANALYZERS
from scripts.run_analysis_budgets_pr62 import validate_analyzer_inventory


@pytest.mark.parametrize("mode", ["complete", "missing", "unexpected", "substituted"])
def test_fresh_extraction_analyzer_inventory(mode):
    reports = {name: {} for name in ANALYZERS}
    assert "bitwise_dependencies" in reports
    if mode in ("missing", "substituted"):
        reports.pop("bitwise_dependencies")
    if mode in ("unexpected", "substituted"):
        reports["unknown_analyzer"] = {}
    if mode == "complete":
        validate_analyzer_inventory({"analyzers": reports})
    else:
        with pytest.raises(AssertionError):
            validate_analyzer_inventory({"analyzers": reports})
