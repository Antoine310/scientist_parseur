# PR57 — elaborated constant selector positions

Recover the two generated bit reversals missed by the frozen PR56 ALU
annotation corpus. Keep benchmarks/annotations/pr56.json unchanged.
The baseline had one of 65 positive bit positions retrieved, zero
labelled false positives and 64 labelled false negatives.

## Implementation

slang v12.1 represents each active generate-loop iteration with a
local Parameter of integer type and the genvar's elaborated value
(BlockSymbols.cpp, GenerateBlockArraySymbol::fromSyntax).
ParameterSymbol::serializeTo emits value and isLocal; NamedValue
references use semantic address and name. Neither address nor a
folded constant field alone is an independent proof of identity.
Resolve direct lexical localparams by exact identity, reset at each
instance, skip inactive generate blocks, and reject conflicting
identities and unknown scopes beyond the bounded map.

Normalize only supported selector expression paths in continuous
assignments. Integer literals, resolved localparams, typed conversions
and bounded nonnegative Add/Subtract/Multiply are accepted when each
intermediate result fits its declared type without wrapping. A supplied
constant field must agree with the computed result. Negative values,
unknown bits, unsupported types/operators, runtime references,
overflow, dynamic or nested selectors, and indexed part-selects remain
outside this extension. The existing strict bit graph gate and declared
packed-bound validation still apply. Original AST is not modified;
legacy bit-access extraction remains as before when normalization
cannot establish both sides of an assignment. No expansion of
procedural loops or arbitrary function evaluation is implemented.

## Acceptance

* Frozen PR56: fixture signal 10/10, fixture bit 16/16, ALU signal
  10/10, ALU bit 65/65 labelled positives; zero labelled FP.
* Separate generated pair-reversal fixture with two module instances:
  exact 16 local bit edges, no cross-instance edges, two dynamic
  selections retained as partial. Verilator/cocotb checks 256
  input vectors with varying selector (not the Cartesian product).
* Unit cases cover lexical identity, runtime tags, conversions,
  invalid values, arithmetic bounds, range endpoints and AST immutability.
* Existing CI regressions must pass.

This is a targeted repair on the development corpus. The separate
fixture checks generalization to another generated mapping, but is
not a blinded or statistically representative holdout. No inference
of whole-ALU precision, functional influence or full CPU coverage.

## Reproduce

    python -m pytest -q -rs tests/test_constant_indices_pr57.py
    python -m pytest -q -rs
    python -m scripts.run_constant_indices_pr57 --out reports/pr57

Report: reports/pr57/run-*/constant_indices.result.json.
Nested annotation results, per-label findings, source graph and
simulation XML remain available. The report is written only after
all assertions succeed; new run directories preserve previous results.
Actual local and CI results are pending.
