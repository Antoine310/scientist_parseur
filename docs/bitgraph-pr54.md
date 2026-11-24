# PR54 — assignment-local bit dependency graph

The additive bit_dependency_graph section expands the existing bit_accesses
positions into individual candidate source/target bit edges. Every edge
has an assignment_id linked to its assignment provenance, guards, event
metadata and nonblocking flag where available. Constant destination lanes
are kept separately without inventing a signal source or constant value.

Only explicitly declared scalar or one-dimensional descending packed
logic/bit types are accepted. Actual declared indices (including nonzero
lower bounds) are used. Each assignment's RHS segments must cover the
destination width exactly, without overlaps or holes, and all selected
positions must be within declaration bounds. A row is accepted atomically.
A stricter AST gate accepts direct nonnegative literal positions and
Simple ranges, not indexed part-selects, nested selections, dynamic
indices or uncertain conversions of index expressions. Unpacked arrays
and unknown layouts are rejected. BitwiseNot remains explicitly marked;
a positional reference does not mean value equality. The legacy
bit_accesses scope remains unchanged: whole-to-whole copies without
selection/concatenation may be absent, and ports are not expanded here.

This is not a full bit-level dataflow engine: no composition across
assignments, global driver completeness, final NBA priority, CDC,
functional influence or timing proof is inferred. Bounds limit the
number of edges; rejected rows retain a reason. No global coverage
percentage is reported.

The fixture tests permutation, nonzero target bounds, inversion,
replication, literal lanes, and negative cases (dynamic index, indexed
part-select and unpacked array). Real slang must reproduce the 24
independently reviewed edges exactly, with four constant target bits and
no edges for the unsupported cases. Verilator/cocotb exercises all 256
values of the eight-bit input with a varying selector, not all combinations
of input and selector. Simulation is distinct from static candidate
validation; formal proof is not performed.

Reproduce:
    python -m pytest -q -rs tests/test_bitgraph_pr54.py
    python -m scripts.run_bitgraph_pr54 --out reports/pr54

Reports: bitgraph.result.json, bitgraph.diagnostic.json,
rtl_dependencies.json, simulation/simulation_results.xml.
Actual EDA results and CI pending. MCP exposure and processor-scale
evaluation are follow-ups.
