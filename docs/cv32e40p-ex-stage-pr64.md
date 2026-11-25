# PR64 — official CV32E40P execution-stage hierarchy

Evaluate the real cv32e40p_ex_stage at pinned upstream commit
b353438ff469c030c89f6804f3b24a2852880e8b, default FPU=0 and
COREV_PULP=0. Eight source files: two packages, ALU and its three
submodules, multiplier and EX stage. The active six instances are
EX, alu_i, alu_i.popcnt_i, alu_i.ff_one_i, alu_i.alu_div_i, mult_i.
The disabled FPU/APU dispatcher is outside the selected configuration.

Use the PR63 read-only snapshot mechanism with one additional verified
blob pin. The original fixture lock and PR63 label inventory stay
unchanged. The additional-pin API rejects overlap and unsafe paths.
No official RTL changes, no wrapper substituting for real EX logic,
no semantic engine changes.

## Static validation

44 source-derived direct signal labels (36 positive, 8 negative)
from the EX-stage source, selected before execution. Includes 21
positive direct port bindings, forwarding guards/data, LSU writeback,
branch/jump, EX/WB register event/data links and ready logic.
Exact active instance paths, selected port directions and all graph
edge endpoints are checked. Strict score gate for these labels only.
Five bounded observed combinational graph paths cross input and output
port boundaries (ALU A/B and multiplier A/B to forwarding data,
ALU A to branch decision). Paths may include data and control edges;
sequential and event edges are excluded. Bounded path observations
do not prove reachability of a condition or functional influence.
Report all ten analyzer diagnostics and retain actual truncation flags;
no full-core coverage claim.

## Behavioral validation

Verilator/cocotb directly on the official EX stage with all top
inputs initialized and a reset pulse. 64 deterministic operand triples,
six sampled scenarios per triple (384 scenarios): XOR forwarding and
jump target, equality branch, integer multiply-accumulate, multiplier
priority over ALU, CSR priority over both, separate LSU writeback data
and branch-ready override. Opcodes from the pinned package.
Two-state combinational samples after reset, not exhaustive simulation,
not instruction execution, not a proof of EX/WB temporal behavior or
global priorities. The overlapping enables are deliberately selected
local mux probes, not a claim that such instructions occur in a core.

## Reproduce

    python -m pytest -q -rs tests/test_cv32e40p_ex_stage_pr64.py
    python -m pytest -q -rs
    python -m scripts.run_cv32e40p_ex_stage_pr64 --out reports/pr64

Report: reports/pr64/run-*/ex_stage.result.json. Failure diagnostics,
static AST, graph, index and simulation XML remain in the fresh run
directory. Official checkout and snapshot blobs verified before/after.
16 targeted unit cases, six instances, 44 labels, five paths and
384 sampled scenarios expected. Local and CI validation pending.
Next: elaborate the actual core with one coordinated configuration,
record limits and unsupported constructs explicitly; do not extrapolate
the EX-stage evidence to the complete processor.
