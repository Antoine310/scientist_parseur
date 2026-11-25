# PR59 — bounded static procedural loop expansion

Add a separate static_loop_expansion report, preserving historical graph
edges, bit accesses, complex_constructs and frozen evaluation labels.

## Supported subset

Direct loops in AlwaysComb procedures, including sequential Block/List
wrappers. A ForLoop must be immediately preceded by its linked
VariableDeclaration in the same statement block. Its declaration is
an automatic signed int/ integer with a nonnegative literal initializer.
The stop is i < literal or i <= literal, and the single step is ++i
or i++. Both references must match the exact iterator symbol identity.
A RepeatLoop requires a nonnegative integer literal count.

The body is a single plain blocking assignment between two distinct
resolved signals, each with a scalar or a direct selected bit of a
proven descending packed declaration. Selectors may use the bounded
typed arithmetic from PR57 and the current iterator value. Expansion
is atomic: a bad position in any iteration rejects the entire loop.
No source AST is mutated and no semantic address is persisted.

Maximum 64 iterations per loop, 2000 loop records, 16384 position
records, and bounded traversal. Runtime bounds, decrement/other steps,
compound assignments, NBA, unsupported types, calls, nested selectors,
self reads, invalid bit positions and unsupported bodies are rejected.
Nested/conditional/timed loops are outside this traversal; the
complex_constructs inventory remains available. This is a first subset,
not an exhaustive inventory of every loop.

Output records include loop ID, iteration ordinal, iterator value
(or null for repeat), source and target positions. Repeated writes
remain separate iteration records. No inference of final values,
global drivers, timing, scheduling or functional influence.
An explicit zero-iteration header produces no position records.

## Validation

Separate RTL fixture:
- for i=0; i<8; i++ : reverse eight bits;
- for j=0; j<=7; ++j : identity eight bits;
- repeat(3): three writes to the same scalar;
- repeat(runtime): partial;
- repeat(65): partial (per-loop budget).

Expected 5 loops, 3 supported, 2 partial, 19 exact iteration
positions (17 unique source-target positions). Verilator/cocotb checks
768 vectors (all 256 data values and counts 0, 1, 7), including
behavior of the rejected cases. This is fixture-only two-state
simulation, not a proof. No change in the official ALU partial-bit
counter is claimed.

    python -m pytest -q -rs tests/test_static_loops_pr59.py
    python -m pytest -q -rs
    python -m scripts.run_static_loops_pr59 --out reports/pr59

Report: reports/pr59/run-*/loops.result.json.
Separate diagnostic, graph and simulation XML remain available.
New run directories preserve older reports.
Local real slang shape and CI results remain to be confirmed.
