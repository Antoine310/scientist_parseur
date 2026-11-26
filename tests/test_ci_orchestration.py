"""Contract checks for the deliberately regular CI orchestration YAML.

This is not a general YAML parser or a substitute for GitHub's validation.
"""
from pathlib import Path
import re

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
HISTORICAL = set("""
analysis-budgets-pr62
analyzer-row-budgets-pr68
annotated-pr56
array-pr60
bit-refinement-pr61
bit-width-pr69
bit-width-pr70
bitgraph-pr54
bitwise-pr72
cocotb-simulation
complex-pr53
constant-indices-pr57
cv32e40p-alu-real
cv32e40p-core-pr65
cv32e40p-diagnostics-pr67
cv32e40p-ex-stage-pr64
cv32e40p-multi-unit-pr63
cv32e40p-popcnt-eqy
cv32e40p-real
cva6-cj-verilator-oracle
cva6-cli-verilator-oracle
cva6-compressed-decoder
cva6-compressed-verilator-oracle
cva6-lane-evidence
cva6-ras
dynamic-pr74
eqy-equivalence
function-pr58
hierarchy-pr52
intercycle-pr51
mcp-stdio
mux-pr73
packed-coordinates-pr71
priority-pr47
reset-formal-pr48
rtl-benchmark
rtl-fixtures
rtl-security-lab
sby-formal
scalability-pr55
selector-recovery-pr75
slang-integration
static-loops-pr59
typed-layout-pr76
unknown-rtl-validation
""".split())


def test_every_historical_workflow_is_called_once_after_python():
    main = (WORKFLOWS / "ci.yml").read_text()
    files = {p.stem for p in WORKFLOWS.glob("*.yml")} - {"ci"}
    assert HISTORICAL <= files
    calls = re.findall(
        r"^  ([\w-]+):\n    needs: unit-tests\n    uses: \./\.github/workflows/([\w-]+)\.yml$",
        main, re.M,
    )
    assert len(calls) == len(files)
    assert set(calls) == {(name, name) for name in files}
    for name in files:
        header = (WORKFLOWS / f"{name}.yml").read_text().split("\njobs:", 1)[0]
        assert re.search(r"^on:\n  workflow_call:\n  workflow_dispatch:\n", header, re.M)
        assert not re.search(r"^  (push|pull_request|pull_request_target):", header, re.M)


def test_final_gate_depends_on_every_validation():
    main = (WORKFLOWS / "ci.yml").read_text()
    gate = main.split("\n  full-validation:\n", 1)[1]
    needs = gate.split("    needs:\n", 1)[1].split("    runs-on:", 1)[0]
    items = re.findall(r"^      - ([\w-]+)$", needs, re.M)
    files = {p.stem for p in WORKFLOWS.glob("*.yml")} - {"ci"}
    assert len(items) == len(files) + 1
    assert set(items) == files | {"unit-tests"}
    assert "if: ${{ always() }}" in gate
    assert f'length == {len(items)} and all(.[]; .result == "success")' in gate


def test_automatic_events_and_concurrency_are_centralized():
    main = (WORKFLOWS / "ci.yml").read_text()
    assert "on:\n  pull_request:\n  push:\n    branches: [main]\n  workflow_dispatch:\n" in main
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in main
    assert "github.event_name == 'pull_request' && github.ref || github.run_id" in main
