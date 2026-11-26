# PR75 — Bounded lexical constant selectors

## Measured baseline

PR74 merged at 59d210f97cdbec4957a31ddf35ab409bacd7d192.
1040 local tests, 44/44 CI, 746/1199 minimum linked support on core,
318/479 on standalone ALU. One new FIFO row, 128 candidate edges,
zero truncation. Artifact 15099683751 (run 45782588756) identifies
all 63 unproven_selector_type residuals in the same ff_one instance,
not runtime indices: line 57 (1), 63 (15), 64 (15), 73 (16), 74 (16).
An independent AST audit resolved the 63 LHS selector expressions
using lexical parameter identities. Full relation output is not yet
validated. Six other core dynamic residuals remain.

## Design and boundaries

Extend constant_indices.evaluate with explicit allow_power opt-in.
Positive integer base, nonnegative exponent at most 10, values at most
1024, identical base/result type, each intermediate fits its declared
type; reject overflow, negative or unknown inputs, mismatched tags and
unbound or mismatched symbol identities. Legacy default remains exact.
No folded constant tag alone provides proof.

selector_recovery is a linked recovery pass, not a replacement logic
engine. Scope: flat-partial rows refused by PR74 as unproven_selector_type.
Private bounded AST-path rewrite only for selectors newly proven by
Power evaluation, preserve elaborated integer type. Persist path, type,
index and proof class, not unstable addresses. Reuse PR72 bitwise and
PR73 mux expanders, or PR71 strict fixed coordinates and literal-chain
validation. Separate fixed positions, bitwise candidates and mux roles.
No runtime selector alternatives, value or functional influence proof.
All previous channel outputs remain byte-for-byte semantically equal
on the same AST/index. Explicit caps and atomic failures. Fresh graphs
have 14 analyzer reports; legacy artifacts without the new pass remain
readable. Historical PR74 comparison disables this pass explicitly.

No alias/enum name guessing, struct/union layout inference, signed
runtime selector handling, arbitrary operator evaluation, or feasibility
and temporal proof. These topics remain in backlog v1.9, with dedicated
type/layout work proposed for PR76 and arithmetic PR77.

## Validation gates

34 targeted cases expected: power opt-in, limits and malformed proof
inputs, lexical identity, private rewrite, fixed/literal/bitwise/mux
delegation, refusal, unchanged previous channels and atomic budgets.

Real generate fixture: 5 assignments, 4 bitwise candidates, 16 mux
data candidates, 8 mux control candidates and one constant position.
1024 two-state input vectors and 3072 checks. Not a four-state proof.

Same AST/index benchmark against measured PR74 inventories. Independent
source oracle derived from cv32e40p_ff_one.sv at pinned commit
b353438ff469c030c89f6804f3b24a2852880e8b, LEN=32, NUM_LEVELS=5:
line 57 constant target sel_nodes[31]; lines 63/64 internal nodes
0..14 use children 2*i+1 and 2*i+2; lines 73/74 leaf nodes 15..30
use input/lut indices 2*(i-15) and the following index. Exactly 31 OR
rows (62 candidates) and 31 mux rows (310 data, 155 control), plus
one constant row. Check exact coordinates, branch IDs and paths in
both ALU and core. 527 edges and one constant position expected per
context; do not add the standalone ALU to the whole core. Require
63 new unique links and zero truncation, frozen prior graphs and
annotations. Expected minimum combined support 809/1199 on core and
381/479 on ALU; actual gains to be measured. This is representation
support within an inventory, not full RTL coverage.

    python -m pytest -q -rs tests/test_selector_recovery_pr75.py
    python -m pytest -q -rs tests/
    python -m scripts.run_selector_recovery_pr75 --out reports/pr75

Share only the compact summary:
    cat "$(ls -td reports/pr75/run-*/ | head -n 1)summary.json"

Detailed selector_recovery.result.json remains in the CI artifact.
Expected 1074 total tests, 45 PR workflows. Local/CI validation pending.
No changes to official RTL.
