# PR65 — First pinned CV32E40P whole-core evaluation

## Objective and configuration

Elaborate the actual cv32e40p_core at the same official revision
b353438ff469c030c89f6804f3b24a2852880e8b as PR63/64. Use the
coordinated default integer configuration:

- COREV_PULP=0, COREV_CLUSTER=0, FPU=0, ZFINX=0.
- FPU_ADDMUL_LAT=0, FPU_OTHERS_LAT=0, NUM_MHPMCOUNTERS=1.
- Official FF register-file implementation.
- Official behavioral clock-gate implementation (simulation model,
  not intended for ASIC/FPGA synthesis).
- No assertion macro, FPU integration, top-level tracer or testbench
  wrapper. Disabled HW-loop, PMP and APU-dispatch blocks are not
  active instances. This is one full core configuration, not every
  variant or a complete SoC.

Use the pinned official manifest order through core, plus the official
clock gate. The 28 compiled SystemVerilog files and manifest are
verified against the Git tree and blob bytes, materialized into a
fresh report-local snapshot using PR63/64. The original fixture lock,
official checkout and old benchmark sources are unchanged. No RTL
edits, stubs or replacement behavioral logic. The 17 additional pins
include the EX-stage pin already established by PR64 and the manifest;
there are 29 verified files in total. Paths and parameter values in
the actual elaborated hierarchy are checked.

## Static evidence and resource measurements

Expected 24 active instances, 23 distinct module definitions, exact
instance-to-module identities, selected top-level port directions and
graph endpoint integrity. 47 manually source-derived signal labels
(39 positive, eight negative), covering clock/reset, instruction
fetch, ID/EX operands, forwarding, LSU, CSR, interrupt/debug and
separate instruction/data memory interfaces. Labels are established
before execution, not a blinded or representative corpus. Keep every
TP/TN/FP/FN and unlabelled prediction; report misses rather than force
a perfect score. Seven bounded combinational path probes record
observed, not_observed or budget_exhausted. No sequential/event
edges in these probes; absence of an observed path is not proof of
independence. These are syntactic paths, not feasible execution paths.

Run in one fresh Linux worker using PR55 measurement protocol:
slang subprocess, AST reload, structural index, graph construction,
serialization and fingerprint timings, file sizes and Python/slang
peak RSS in KiB. Peak RSS values are separate process measurements,
not simultaneous total memory. One sample is an initial observation,
not a stable performance distribution. Retain all ten analyzer limit
reports and partial reasons, with existing budgets unchanged.
A budget refusal or failed structural check is a failed run, with
phase and error preserved. Successful generation with observed
analyzer truncation is distinguishable from completeness.

## Reproduce

    python -m pytest -q -rs tests/test_cv32e40p_core_pr65.py
    python -m pytest -q -rs
    python -m scripts.run_cv32e40p_core_pr65 --out reports/pr65

Optional --timeout 10..600 seconds (default 180) bounds the slang
subprocess, with an outer fresh-worker timeout of timeout+120.
Report: reports/pr65/run-*/core.result.json.
The static directory retains the manifest-derived AST, graph, index,
worker sample and slang diagnostics. Fresh run directories preserve
historical evidence. Official checkout and materialized source
blobs are verified before and after successful evaluation. If a local
partial clone lacks an object the snapshot fails explicitly instead
of silently fetching or altering the checkout.

20 targeted unit cases, 24 instances, 47 annotations, seven path
probes and one resource sample planned. CI uses real pinned slang
and the existing verified fixture installer. Actual local and CI
results are pending. No new processor simulation, software execution,
functional proof, design coverage or security claim. No semantic
engine or existing analysis-budget change in this PR. The next work
should be selected from the measured whole-core limitations.
