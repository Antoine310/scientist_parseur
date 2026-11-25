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
  the selected declared destination width, and every source leaf
  is validated against its declaration before resizing. Truncation
  keeps low positions; extension requires unambiguous signedness.
  Do not infer resizing from a size mismatch alone or flatten array
  elements. Preserve old reasons when the retry cannot be validated.

The separate enable_width_literals=False policy reproduces PR69;
enable_width_conversions=False reproduces the PR68 positional policy.
All caps remain unchanged. Prior supported graph rows and edges are
preserved. Additional width evidence is recorded in width_conversions.
No claim of exact values for constant_target_bits, global writers,
functional influence, timing or whole-design coverage.

## Validation

31 new unit cases: literal width and invalid forms, X/Z constant
positions (static only), constant state conversion, refusal of
dynamic state conversion, typed assignment extension/truncation,
untyped/incorrect/out-of-bound/layout/compound rejection, preservation
of prior support and rejection of an invalid source even if discarded
by truncation.

Real slang fixture: 4 dynamic position edges, 18 constant target
positions; exhaustive 256 input values, 768 behavioral checks in
Verilator/cocotb (two-state, not proof of X/Z behavior). Frozen PR56
annotations and PR65 labels/paths are exercised through the PR67
reference runner.

Same AST and index comparison of PR68, PR69, PR70 on official ALU
and whole core. Exact historical bit counts for both older policies.
Require unchanged non-target graph, stable assignment identity,
preserved supported rows/edges, no new bit truncation, and at least
one additional recovered official assignment. Report each recovery
with source, target, reason, modes, dynamic edges and constant lanes;
summarize separately for PR69 and PR70 by owning instance. Actual
gains unknown until measured. Historical PR69 runner keeps its
original comparison by explicitly disabling the newer policy.

    python -m pytest -q -rs tests/test_bit_width_pr70.py
    python -m pytest -q -rs
    python -m scripts.run_bit_width_literals_pr70 --out reports/pr70

Report: reports/pr70/run-*/bit_width_literals.result.json.
Expected 31 targeted / 911 total tests and 40 PR workflows; local
and CI validation pending. No official RTL changes. Remaining
dynamic state conversions, ambiguous signedness, unsupported
layouts, operators and unaccounted exclusions remain open in
docs/rtlprep-backlog.md. Reassess after real measurements.
