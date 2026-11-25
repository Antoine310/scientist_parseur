# PR70 — Typed literals and verified assignment resizing

## Scope and method

Second part of PR61-BIT-02, PR69-WIDTH-02. The measured PR69
baseline is 1 199 captured bit assignments, 528 supported, 671
partial, 2 842 dynamic bit edges. The ALU hierarchy remains
479/254/225/477. The 61 PR69 recovered assignments added no dynamic
edges; do not equate them with new signal dependencies.

Run the PR69 extraction first. Preserve its supported mappings
unchanged. Retry only selected width/literal failures on already
captured rows (no change to assignment eligibility). Retry requires
the strict positional gate, an ordinary untimed, non-compound
assignment and supported procedural context. The new cases:

- IntegerLiteral with an elaborated integral type and a recognized
  serialized literal; UnbasedUnsizedIntegerLiteral with an elaborated
  width and recognized serialized value. Slang v12.1
  UnbasedUnsizedIntegerLiteral::getValue fills the elaborated width
  and serializeTo writes that value (LiteralExpressions.cpp).
  Do not assume width one for every '0/'1/'x/'z.
- Explicit conversions between state domains only where every
  segment is constant (no runtime source). This is position metadata,
  not a model of X/Z conversion or a constant-value evaluator.
  Ambiguous widening signedness remains rejected.
- Explicit integral whole-source widths previously unrecognized
  by the narrow legacy type parser.
- Assignment width adaptation only when RHS segment width agrees
  with its explicit elaborated integral type, LHS type agrees with
  the selected declared destination width, the Assignment AST itself
  carries the matching integral type, no unary transform is being
  implicitly resized, and every source leaf
  is validated against its declaration before resizing. Truncation
  keeps low positions; extension requires unambiguous signedness.
  Do not infer resizing from a size mismatch alone or flatten array
  elements. Preserve old reasons when the retry cannot be validated.

- For selected width failures in procedural blocks, retry selectors with
  the existing bounded lexical parameter evaluator. Preserve old rows
  if the retry fails. Only exact visible declaration identities qualify,
  not runtime constant tags, sibling scopes or guesses about loop
  execution. The original PR40 unary metadata remains unchanged.

The separate enable_width_literals=False policy reproduces PR69;
enable_width_conversions=False reproduces the PR68 positional policy.
All caps remain unchanged. Prior supported graph rows and edges are
preserved. Additional width evidence is recorded in width_conversions.
No claim of exact values for constant_target_bits, global writers,
functional influence, timing or whole-design coverage.

## Validation

37 new unit cases: literal width and invalid forms, X/Z constant
positions (static only), constant state conversion, refusal of
dynamic state conversion, typed assignment extension/truncation,
untyped/incorrect/out-of-bound/layout/compound rejection, preservation
of prior support and rejection of an invalid source even if discarded
by truncation. The six additional tests cover the historical unary
metadata and a proven genvar index plus four negative scope/identity
cases.

Real slang fixture: 4 dynamic position edges, 21 constant target
positions (including three generated procedural assignments); exhaustive
256 input values, 1024 behavioral checks in
Verilator/cocotb (two-state, not proof of X/Z behavior). Frozen PR56
annotations and PR65 labels/paths are exercised through the PR67
reference runner.

Same AST and index comparison of PR68, PR69, PR70 on official ALU
and whole core. Exact historical bit counts for both older policies.
Require unchanged non-target graph, stable assignment identity,
preserved supported rows/edges, no new bit truncation, and the three independently reviewed CSR reset-write positions at line 1529
of cv32e40p_cs_registers.sv (mcountinhibit_q[0], [2], [3]) and at
least one additional recovered official assignment. Report each recovery
with source, target, reason, modes, dynamic edges and constant lanes;
summarize separately for PR69 and PR70 by owning instance. Actual
gains unknown until measured. Historical PR69 runner keeps its
original comparison by explicitly disabling the newer policy.

    python -m pytest -q -rs tests/test_bit_width_pr70.py
    python -m pytest -q -rs
    python -m scripts.run_bit_width_literals_pr70 --out reports/pr70

Report: reports/pr70/run-*/bit_width_literals.result.json.
Expected 37 targeted / 917 total tests and 40 PR workflows; local
and CI validation pending. No official RTL changes. Remaining
dynamic state conversions, ambiguous signedness, unsupported
layouts, operators and unaccounted exclusions remain open in
docs/rtlprep-backlog.md. Reassess after real measurements.

## First execution and root-cause audit (25 November 2026)

Original head 6ef5d6a75418a35696e2a3866fa1a80015531bae:
31 targeted tests passed, full local suite 910 passed / 1 failed,
simulation 256 vectors and 768 checks passed, ALU and core counts
unchanged (479/254/225/477 and 1199/528/671/2842). The runner
correctly failed its recovery gate. CI 37 successful / 3 failed;
Python unit and CVA6 compressed-decoder runs failed the same
PR40 value_transform assertion; PR70 benchmark failed the gain gate.
Do not waive either failure.

The historical PR40 test has a one-bit inverted RHS and an eight-bit
target in a synthetic AST without Assignment.type. The initial
retry replaced its RHS-only metadata by a zero-extended mapping,
changing the first segment. Require an explicit assignment type
and reject implicit resizing of existing unary transformations;
retain the old test unchanged.

Audit of the actual GitHub CI AST and graph from run 45629165734,
artifact 15030894309 (same original head, pinned official RTL).
For each of 259 width/literal-related partial rows, match AST
assignments by instance, file, source line and root target name;
classify a group as multidimensional only when every matching
candidate has a selection with a multidimensional base type.
This is a source-location grouping, not a unique AST ID join.
Results: 165/165 target_rhs_width_mismatch, 29/29
conversion_state_change_unmodeled, 9/9 unbased literals and 43/55
conversion_width_unproven_or_changed involve multidimensional
selections; 246/259 in total. Several also involve calls/operators.
Do not treat these as ordinary width errors or flatten arrays
into false bit positions. Remaining 12 conversion and one source
width rows include scalar genvar selections, binary ops and aliases.
The three scalar genvar reset writes are targeted by this revision;
the benchmark still requires real recovery. Actual revised results
are pending.

PR69 detail confirmed: all 61 recovered rows are CSR constant
truncations, 61 constant target positions, zero dynamic edges.
