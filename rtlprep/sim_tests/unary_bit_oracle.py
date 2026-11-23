"""Independent two-state behavioral reference for the PR40 unary-bit RTL.

The expected outputs below are computed directly from a human-audited RTL
contract, *never* from RTLPrep's AST, dependency graph or bit_accesses index.
This verifies simulation behavior on covered stimuli, not exhaustive 4-state
SystemVerilog semantics, a core-level CVA6 decoder, or functional accuracy of
all dependency relations.
"""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer


def expected_outputs(instr: int, enable: int) -> dict[str, int]:
    """Independent integer truth table for unary_bit_pr40 (16-bit inputs)."""
    assert 0 <= instr < (1 << 16) and enable in (0, 1)
    return {
        "bit_o": 0 if instr & 0x8000 else 1,
        "mix_o": (instr & 0xFF) ^ 0x10,
        "wide_o": (instr ^ 0x000F) & 0x000F,
        "logical_o": int(bool(enable) and not bool(instr & 0x0008)),
        "reduction_o": int(bool(enable) and (instr & 0x00F0) == 0x00F0),
    }


async def check_vector(dut, instr: int, enable: int) -> None:
    dut.instr_i.value = instr
    dut.en.value = enable
    await Timer(2, unit="ns")
    expected = expected_outputs(instr, enable)
    for port, value in expected.items():
        observed = int(getattr(dut, port).value)
        assert observed == value, (
            f"independent oracle failed: instr_i=0x{instr:04x} en={enable} "
            f"port={port} expected=0x{value:x} observed=0x{observed:x}"
        )


@cocotb.test()
async def test_directed_boundaries_and_guard_branches(dut):
    # Both guard outcomes and important bit positions; includes values
    # which make a wrong un-inverted bit_o fail immediately.
    vectors = (0x0000, 0xFFFF, 0x8000, 0x7FFF, 0x0010, 0x0008,
               0x00F0, 0x0FF0, 0x0080, 0x0100, 0x55AA, 0xAA55,
               0x000F, 0x00FF, 0xFF00, 0x1234, 0xC0DE)
    for instr in vectors:
        for enable in (0, 1):
            await check_vector(dut, instr, enable)


@cocotb.test()
async def test_exhaustive_low_byte_with_both_high_bit_values(dut):
    # Exhaust low 8 bits plus independently toggle bit 15, and both
    # conditional branches: 256 * 2 * 2 = 1024 simulation vectors.
    # Middle bits are held deterministic, not all 65,536 inputs tested.
    for low in range(256):
        for high_bit in (0, 1):
            instr = low | (0x8000 if high_bit else 0) | (
                ((low * 37) & 0x7F) << 8
            )
            for enable in (0, 1):
                await check_vector(dut, instr, enable)


@cocotb.test()
async def test_seeded_full_width_patterns(dut):
    rng = random.Random(0x41CA6)
    for _ in range(256):
        await check_vector(dut, rng.randrange(1 << 16), rng.randrange(2))
