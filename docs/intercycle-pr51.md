# PR51 — intercycle candidate dependencies

The new graph section derives from existing sequential candidates, never
from guessed signal names. For each supported local syntactic path it
records the final NBA's data references separately from guard references,
or an explicit local unwritten/hold candidate, with event and source
provenance. One event step is not a guaranteed cycle count. Multi-event
processes retain their raw events; no clock or reset is guessed.

Bounded backward traces traverse only single-edge rows with identical
event identity. They stop at unresolved, partial or different-event
boundaries; feedback may recur at a different step. A path may combine
syntactic alternatives without proving their joint feasibility. No CDC,
global writer completeness, combinational propagation, exact latency,
or bit-level functional influence is inferred. Unknown RHS, multiple
observed FF writers and truncated upstream analyses are conservative
partial results. The new graph section is additive; MCP exposure and
hierarchical propagation are deferred.

The RTLPrep-owned fixture exercises a three-register pipeline, conditional
hold, and a second event domain. Real slang must recover the candidate
chain and stop at the event boundary. Cocotb checks 64 cycles after three
warm-up edges, with enable changes and separate other-clock edges. This
is fixture-level behavioral validation, not real CPU latency or a proof.

Reproduce:
    python -m pytest -q tests/test_intercycle_pr51.py
    python -m scripts.run_intercycle_pr51 --out reports/pr51

Report: reports/pr51/intercycle.result.json and rtl_dependencies.json.
Results pending actual EDA and regression CI.
