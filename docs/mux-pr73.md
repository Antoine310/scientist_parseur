# PR73 — Mux data and control provenance

## Scope

PR72 validated at 6e3ab2f: 977 tests and 42/42 PR CI; core
minimum combined representation support 706/1199 (531 flat,
151 linked PR71, 24 linked PR72); 493 without linked support.
ALU 290/479. PR73 is based on that tested commit. The ready-for-review
transition of PR72 returned GitHub API errors during preparation;
do not claim it merged until confirmed.

The mux_dependencies channel handles previously captured flat-partial
assignments with an explicit root ConditionalOp (or a validated
equal-width, same-state conversion around it), including a bounded
tree of nested conditional arms. Use the same declaration identity,
fixed packed coordinates and bitwise expression validation as
PR71/72. Conditions support one expression, integral truth tests,
equal-width comparisons and logical AND/OR/NOT over supported
expressions. Reject pattern conditions, multiple conditions, dynamic
selectors, opaque types, unsupported operators, width-changing
dynamic conversions and unsupported procedural contexts. Muxes
embedded under arbitrary other expressions are outside this scope.

Each assignment has decision IDs (with parent path, operator/type
and relative RHS AST path) and leaf branch IDs (with ordered
decision/arm path). Data edges refer to a branch ID; control edges
refer to a decision ID. Data candidates are lane-specific; a condition
leaf may affect every destination lane. Repeated source coordinates
are deduplicated within a branch/decision, never across distinct
paths or roles. Branch constant_target_positions mean absence of
dynamic RHS leaves in that arm, not a computed value or a constant
output. Do not prune branches even when a condition is constant.
The true/false arm labels name syntax, not feasible Boolean guards;
an unknown four-state condition can merge both arms. No inference
of satisfiability, functional influence, actual priority, final
writer or time. Existing procedural guard/event/NBA metadata is
preserved, not interpreted.

Existing captured flat assignment ordinals are the cross-channel
identity. No AST address is persisted. Keep flat, array, bitwise and
signal graphs exact. Bounded depth/nodes, branch count, row pair
budget and shared edge/constant-position cap; failures are atomic.
Report new analyzer limits; 12 analyzers in fresh graphs; legacy
v1 graphs without new channels remain readable. Historical PR69–72
policy comparisons disable the mux channel. The shared PR62 fresh
inventory gate compares exact registered names.

## Validation

33 new unit cases: direct/nested mux, comparison and logical
conditions, multibit truth, repeated source across paths, literal
conditions, bitwise arms, negative inputs, old graph identity, budget
atomicity and legacy graph reading.

Real slang fixture: 5 assignments, 6 decisions and 11 arms, 36 data
and 28 control candidate edges, 8 branch-local constant positions.
Exhaustive 1024 two-state input combinations and 5120 output checks
with Verilator/cocotb. No four-state proof.

Same AST and index on official ALU/core, require unchanged prior
flat/array/bitwise inventories, unique links and branch/decision
integrity. Count only new unique support after union with PR71/72.
Source-derived ALU oracle line 961, result_o:
true arm bits 0..15 from operand_a_i, 16..31 from adder_result;
false arm all bits from result_minmax; is_clpx_i[0] control for
all 32 destination positions. Require 64 data + 32 control edges
in both ALU contexts, exact coordinates and paths, at least one
additional row and no truncation. The reference runner retains
frozen prior annotations. Actual gains unknown until measured.

    python -m pytest -q -rs tests/test_mux_pr73.py
    python -m pytest -q -rs
    python -m scripts.run_mux_pr73 --out reports/pr73

Share only the compact summary:
    cat "$(ls -td reports/pr73/run-*/ | head -n 1)summary.json"

Detailed mux.result.json retained in run directory and CI artifact.
Expected 33 targeted / 1010 total tests and 43 PR workflows.
Local/CI validation pending; no changes to official RTL.
