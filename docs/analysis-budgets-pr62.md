# PR62 — global analysis budgets and observed limit diagnostics

Prepare multi-unit and full-core analysis without silently presenting
truncated results as complete. Existing semantic graphs, coverage v1,
and frozen PR56 annotations are unchanged.

## Global gates

The default policy limits an elaborated AST file to 256 MiB before
decoding; the bounded file read also handles growth after stat.
The AST admission gate limits decoded JSON to 3,000,000 values and
depth 128. Graph publication limits the graph before the new report
to 5,000,000 values and depth 128. Each scalar or container counts
as one JSON value, dictionary keys are excluded, root depth is zero.
The iterative traversal uses an iterator stack proportional to depth.
Direct graph API users may supply AnalysisBudget explicitly; the CLI
runner uses defaults. Budget errors are structured with stage, metric,
limit and observed_at_least. No partial graph is published on a gate
refusal by the runner; the previous graph is removed before starting.

These are admission/publication gates, not a hard RSS, CPU, wall-clock,
or disk quota. Slang runs before AST file admission. JSON decoding
allocates memory before the tree gate, and the graph is allocated
before publication admission. The existing per-analyzer limits and
slang subprocess timeout remain in place. The report itself is excluded
from graph metric and limit, and file bytes are not graph values.
The chosen defaults are initial engineering limits, not measurements
of the maximum supported CPU size.

## Unified analysis_limits report

Report all ten record analyzers, their current configured local limits,
captured records, observed status counts, partial-reason histograms,
exclusion counters, top-level truncation, nested truncation flags
within rows and inherited truncation from upstream analyzers.
Separately retain signal-graph warnings and whether the old coverage
findings list is capped. No percentage of design coverage is inferred.
A no-reported-limits assessment means only that no limits were reported
in these scopes. Some excluded constructs do not have emitted records.
The older coverage API is not redefined. Runner deps.result.json exposes
a compact assessment and truncation list without changing the meaning
of status=passed (successful generation, not completeness).

## Validation

26 unit cases: exact boundaries, malformed budget/counts, bounded file
read, early AST rejection, graph publication gate, anonymous nested
truncation, upstream truncation, warnings and immutable inputs.

Real slang probes reuse the independently specified PR55 pipeline
fixture at 8, 512 and 520 stages. The register-flow budget remains 512:
only the 520-stage case must report that analyzer's truncation and
its downstream propagation through sequential/intercycle candidates.
The runner also tests both global gates on the eight-stage AST with
deliberately tiny budgets, without modifying the default policy.
The pinned official ALU must retain 479 assignments, 254 supported,
225 partial, 477 legacy edges. Report the underlying bit_accesses
partial reasons in addition to the legacy graph's generic categories.
This is not another semantic recovery PR; no reduction in the 225
partial rows is claimed.

    python -m pytest -q -rs tests/test_analysis_budgets_pr62.py
    python -m pytest -q -rs
    python -m scripts.run_analysis_budgets_pr62 --out reports/pr62

Report: reports/pr62/run-*/analysis_budgets.result.json.
Official RTL verified before and after, never modified. New run
directories preserve older results. Actual validation pending.

The new workflow installs pinned slang, not Verilator (no new
behavioral simulation in this PR). It cancels superseded in-progress
runs of itself on the same non-main ref. Existing 32 workflows are
unchanged; repository-wide CI consolidation is deliberately separate.
