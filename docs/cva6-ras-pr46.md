# PR46 — real CVA6 return address stack (RAS)

First targeted sequential CVA6 probe at the same pinned upstream revision
742dc82a0c706e0a3bfb98b709fd3ee06d50d12a. The audited module is
core/frontend/ras.sv (blob 422a829fa4c1d4d4fa3b1c78cf38337003887de1).
The harness selects cv32a6_imac_sv32 and depth two; it does not claim to
reproduce all production frontend parameters.

Candidates inspected: branch_unit (combinational), serdiv (FSM and LZC
dependencies), BHT (larger tables), FIFO (generate branches and assertions),
and RAS (compact, packed state and independent observable top).
RAS was selected for its bounded state transition policy:
reset clears state asynchronously; flush clears state on the clock edge;
push shifts; pop removes top; simultaneous push/pop replaces top while
preserving the lower entry; idle retains state.

The existing register_flow and sequential_candidates analyzers are reused.
The report preserves their actual paths, guards, events and coverage, even
if unsupported. It does not infer a reset candidate from a signal name or
claim proof of the combinational stack_d expression. Packed array/member
analysis is deliberately not extended here.

The independent Python model drives a cocotb test with 6 directed cycles,
256 seeded cycles and one explicit final push, checking top address and
valid before and after edges and two reset assertions with clock held low.
Lower entry is observed indirectly on pop. No exhaustive coverage or formal
proof is claimed. Negative mutation control is deferred to the next phase;
the test is a positive behavioral probe, not a per-path validation.
Source hashes and fingerprint are checked around the combined run.

## Reproduce

Ensure the existing sparse checkout includes the real RAS file:
    git -C upstream_cva6 sparse-checkout add core/frontend/ras.sv

    python -m pytest -q tests/test_cva6_ras_pr46.py
    python -m scripts.run_cva6_ras_behavior --source-root upstream_cva6 --out reports/pr46

Reports: static/cva6_ras_report.json, static/rtl_dependencies.json,
ras_simulation.result.json and simulation_results.xml under reports/pr46.
Results pending CI. No changes to official RTL.
