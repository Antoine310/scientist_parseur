# PR60 — fixed array coordinate dependencies

Add an additive array_dependencies report to the dependency graph.
The original signal-level and flat bit graphs, historical annotation
corpus, function summaries and loop expansion remain unchanged.

## Representation and scope

slang v12.1 TypePrinter in its default SystemName style prints
fixed unpacked dimensions after a dollar separator, e.g.
logic[7:0]$[1:2][0:1]. Packed dimensions precede it.
Only explicit logic/bit layouts with nonnegative fixed ranges,
at most four dimensions and bounded storage/leaf width are accepted.
No typedef offsets or dynamic, associative, queue or struct layout
is inferred.

For direct continuous assignments with an array at a root selection
or conversion, resolve the base signal by elaborated identity and
match the declared type. Select every unpacked and outer packed
dimension with a proven constant index, then select the entire final
packed vector, one bit, or a simple range in its declared direction.
Scalar elements use bit zero. Coordinates retain unpacked indices,
outer packed indices, and final bit separately. Right endpoints are
least significant in the selected range, including ascending ranges.

Both sides must have equal selected width. One explicit width-preserving
same-base-type vector conversion is permitted on the RHS. All
positions are checked before emitting any edge. Runtime selector
references are observed separately and never used to fabricate fixed
coordinates. Source/target names and source location are retained on
partial rows where resolved. The selector reference list is a bounded
observation, not an exhaustive influence set.

Limits: 2000 assignment records, 16384 edges, 1024 bits per leaf,
65536 total scalar positions per declared layout, bounded traversal.
No aggregate copy, nested final packed selections, indexed part selects,
arbitrary RHS operators, procedural arrays, global drivers, bit mapping
through ports, timing or functional proof. No claim of complete array
inventory. The separate coordinate graph cannot be added numerically
to the historical flat bit graph.

## Validation

A fixture checks 11 continuous assignments: 10 supported, one
runtime-indexed read partial, 65 independently specified coordinate
edges, no fabricated edge for the runtime read. Includes nonzero
unpacked bounds, a slice, a selected bit, two packed dimensions and
two unpacked dimensions. Verilator/cocotb checks 512 vectors (all
256 a values, b a bijective transform of a, both legal indices).
This is not exhaustive over a and b independently.

The runner also extracts the pinned official CV32E40P ALU, verifies
the original 479 bit assignments / 222 supported / 257 partial /
445 flat edges are unchanged, and records the partial-reason
histogram and new array counters. No independent ALU array oracle
is included; this real-RTL diagnostic is not a measured improvement
in whole-ALU coverage. Official source checkout is verified before
and after the run, never modified.

    python -m pytest -q -rs tests/test_array_pr60.py
    python -m pytest -q -rs
    python -m scripts.run_array_pr60 --out reports/pr60

Report: reports/pr60/run-*/array.result.json. The fixture and ALU
subdirectories retain the AST, graph, diagnostic and simulation XML
where applicable. New run directories preserve old evidence.
Real slang/Verilator and CI validation are pending.

Next: use the real ALU diagnostic to prioritize integration of
coordinate-aware expressions, procedural array selections, and
conservative arithmetic dependency candidates; keep positional,
syntactic and functional evidence distinct.
