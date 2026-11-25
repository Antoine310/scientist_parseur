# PR67 — Diagnostic baseline and backlog evidence

Backlog: docs/rtlprep-backlog.md (introduced in separate PR66).
This PR is based on PR65 until its fusion; the independent PR66 must
also be integrated before final retargeting to main. No backlog IDs
are closed based on unexecuted tests.

| Backlog ID | New evidence planned | Status before validation |
| --- | --- | --- |
| PR65-BIT-01 | Per-instance bit assignment and reason inventory, exact reconciliation | In progress |
| PR61-BIT-01 | Standalone ALU baseline 479 / 254 / 225 / 477; every captured partial listed | Open (inventory only) |
| PR65-WARN-01 | All emitted warning records, reason and owning instance | In progress |
| PR65-COV-01 | Per-instance rows and partial reasons for ten analyzers, exclusions, independent active AST census | In progress |
| PR23-COV-01 | Distinct denominators, explicit unknown bucket and census scope | Open (not full exclusion accounting) |
| PR65-LIMIT-01 | Instrument actual expressions/complex_constructs cap triggers | Open (diagnostic only) |

After validation, append evidence from the report to the permanent
register in a follow-up or during retargeting. Do not close the
semantic debts: this is measurement before correction.

## Method

Re-elaborate the same 24-instance pinned whole core with PR65 and
the standalone four-instance ALU using the same verified snapshot.
All analyzer caps, existing graph edges, annotations and semantics
remain unchanged. Two additive truncation_events fields record the
actual branch hit: expressions row cap and complex_constructs row,
node, depth, list/child queue caps, with first witness per reason.
These are **trigger counts**, not counts of omitted constructs; e.g.
an expressions cap check precedes checking assignment eligibility.
Nested expression/reference truncation remains reported by PR62.
No new process quotas or cap increases.

Partition observed analyzer rows by exact instance field or longest
matching instance prefix of a qualified target. Preserve an explicit
unattributed bucket. Each of ten analyzer inventories reconciles
captured counts, status histogram, clipped partial reason histogram
and nested truncations with PR62. Exclusion counters remain global
unless there is actual row evidence; do not assign them to instances
by guessing. Partial/unknown rows have artifact-local ordinal,
target, actual source line when available and reason. No claim of
stable assignment ID across distinct runs.

The bit graph and bit_accesses have a documented ordinal join:
reconcile every assignment_id, target, edge count and global totals;
record both reasons and use bit-access reason to refine
partial_bit_access. Maintain separate constant-target counts.
Retain original PR56 frozen label scores (signal TP10, bit TP65,
FP/FN0) and the ALU positional counts. The core checks 39/8
positive/negative direct labels and seven observed paths.
Compare the integrated ALU to standalone in the summary, without
requiring identical counts from different contexts.

Independently traverse active procedural and continuous subtrees of
the bounded elaborated AST, excluding inactive generate branches and
declaration/function bodies. Count Assignment AST occurrences
(including constructs outside analyzer eligibility), lhs/rhs kinds,
process context and source locations, and selected calls/loops/
selections/conditionals. This is a **syntax census**, not a shared
denominator, not execution, not an exhaustive list of omitted
assignments or a one-to-one match to analyzer rows. Do not subtract
analyzer row counts from this census to claim unsupported coverage.

Warnings only have context and reason in current graph schema; keep
source null rather than invent a line. The report is not a proof of
functional influence, coverage, or correctness. No new simulation.

## Reproduce

    python -m pytest -q -rs tests/test_cv32e40p_diagnostics_pr67.py
    python -m pytest -q -rs
    python -m scripts.run_cv32e40p_diagnostics_pr67 --out reports/pr67

Outputs:
- reports/pr67/run-*/diagnostics.result.json: full diagnostic evidence.
- reports/pr67/run-*/diagnostics.summary.md: per-instance bit and AST counts.
- Nested fresh core/ALU source and static artifacts, original reports retained.

20 targeted cases planned, 832 total expected from PR65 baseline
812. Actual local and CI results pending. The root causes and counts
of core partial assignments are unknown until the run. Next PR68
uses actual truncation events to select bounded changes; do not
simply raise all caps.
