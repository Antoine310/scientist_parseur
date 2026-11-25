# PR58 — simple function return references

This additive graph section records candidates for syntactic return
references of direct continuous assignments calling local automatic
functions. A function must have only input formals, no defaults, no
unsupported declarations, and a single explicit return expression in
a bounded whitelist (named formal references, integer literals, selected
unary/binary operators, conversions and concatenations). Actual argument
expressions are validated even when unused. Function identity is resolved
by exact semantic address and name within the elaborated instance.
No raw address is persisted.

The report separates used formal positions, unused formal positions,
all actual argument signal references and the subset corresponding to
the return expression. It is not a replacement for existing signal
edges or complex_constructs. Unsupported direct call sites remain
partial, without an asserted return-reference set. Nested calls,
recursive functions, global references, multiple statements, static
functions, output/ref arguments and procedural call sites are outside
this first subset. No whole-design call coverage is claimed.

A syntactic return reference is not functional influence: x ^ x
references x but its two-state output is always zero. No bit mapping,
side-effect analysis for arbitrary functions, timing or proof is
inferred. No official RTL is modified. This PR does not yet reduce the
257 partial bit-access graph assignments observed on CV32E40P ALU.

## Validation

Five direct continuous call sites on a separate fixture: three supported
(mix using only the first argument, both using both arguments, cancel
using x twice), two partial (external read and branching body).
Verilator/cocotb checks 1024 vectors, all 256 b values for each of four
fixed a values. This is not exhaustive over both inputs and does not
prove four-state behavior. The frozen PR56 benchmark and previous
regression workflows remain unchanged.

    python -m pytest -q -rs tests/test_function_pr58.py
    python -m pytest -q -rs
    python -m scripts.run_function_pr58 --out reports/pr58

Report: reports/pr58/run-*/function.result.json.
Actual local and CI measurements remain pending. Further work includes
function summaries on real CPU RTL, nested/conditional returns,
procedural loops and array layout.
