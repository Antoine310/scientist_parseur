# PR52 — hierarchical dependency candidates

Reuse the dependency graph's observed port_input, port_output and
nonsequential data references, plus supported last-NBA and hold paths from
PR51. A backward trace preserves full hierarchical paths, port direction,
locations, event identities and guard provenance. Port references may
include expression controls; they are not bit mappings or equality claims.

The additive hierarchical_event_bindings section records only direct
NamedValue scalar input port connections recognized in the elaborated AST.
These may provide a candidate common event identity across nested
instances, provided the observed incoming edge and binding are unique
and consistent. Expressions, ambiguous bindings and multi-event processes
are not treated as equivalent clocks. This is not a CDC or physical clock
proof. Unknown/partial sequential rows stop the trace, rather than falling
back to a fictitious combinational dependency. Local hold may revisit a
signal at another event step; combinational cycles stop. Hop, event-step
and path bounds limit exploration. No global writer completeness or
guard feasibility is asserted. The result always has guaranteed_cycles=null.

The fixture instantiates two sibling pipeline stages under a parent,
plus a third stage on a distinct event signal. Real slang must recover
a two-NBA candidate chain through nested ports, resolve the direct
shared clock bindings and stop at the other event boundary. Verilator
and cocotb check 64 vectors after two warm-up edges. This is a fixture
validation, not a proof of CVA6-wide hierarchical propagation.

Reproduce:
    python -m pytest -q tests/test_hierarchy_pr52.py
    python -m scripts.run_hierarchy_pr52 --out reports/pr52

Reports: hierarchy.result.json, hierarchy.diagnostic.json,
rtl_dependencies.json and simulation/simulation_results.xml.
Actual validation pending. MCP integration, real processor-scale
hierarchical validation and complex port expression semantics are deferred.
