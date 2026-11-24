# PR53 — complex SystemVerilog construct observations

Add a bounded, additive complex_constructs section to the dependency graph.
The inventory walks active elaborated instances and procedural/continuous
ASTs; it does not treat uncalled subroutine declarations as runtime calls.
Slang v12.1 serializes Call arguments using the arguments field and the
callee link using subroutine. Names are retained without unstable AST IDs.
Each argument's observed signal references are separated; unresolved symbols
remain unknown. The expression index retains argument trees but keeps call
coverage partial. The existing dependency graph does not invent edges from
arguments to the return value.

ElementSelect and RangeSelect observations retain base references and
selector references separately. Direct bounded integer literals are recorded;
runtime selectors, signed ambiguous values and nonliteral indices are not
guessed. These are selection observations, not array layout or bit-lane
mappings. The preexisting bit_accesses semantics are unchanged.

RepeatLoop records a literal header count up to 64; ForLoop records header
references and a literal comparison operand where available. Neither is a
proof of an executed trip count: breaks, side effects, induction-variable
writes, and nested control flow are not modeled. No body unrolling is
performed. All loop execution and function return semantics stay partial.
Traversal and reference budgets explicitly flag truncation.

The RTLPrep-owned fixture includes a function with an unused argument, an
unpacked array with literal and dynamic selectors, repeat and for loops.
The real slang check requires the expected observations, and independent
cocotb checks 64 vectors against the fixture's output behavior. This does
not validate function-body dependencies or actual loop unrolling. No
formal proof or global coverage is claimed; results pending actual CI.

Reproduce:
    python -m pytest -q -rs tests/test_complex_pr53.py tests/test_expressions.py
    python -m scripts.run_complex_pr53 --out reports/pr53

Reports: complex.result.json, complex.diagnostic.json,
rtl_dependencies.json, simulation/simulation_results.xml.
