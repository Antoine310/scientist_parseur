"""Cocotb oracle for the c.j case of the exact upstream CVA6 decoder.

The independent expected result is built from the public RISC-V JAL bit
layout and an audited compressed c.j field mapping, NOT from slang's AST,
RTLPrep bit_accesses, graph edges, or the RTL simulator implementation.
The simulator is tested in two states; not a full CVA6 correctness proof.
"""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer


def encode_cj(payload: int, upper: int = 0) -> int:
    """Force quadrant C1, funct3=101; all 11 payload bits [12:2] may vary."""
    assert 0 <= payload < 2048 and 0 <= upper <= 0xFFFF
    return (upper << 16) | 0xA001 | (payload << 2)


def expected_cj_jal(value: int) -> int:
    """Independent RV32 JAL word construction for c.j (no RTL/AST imports).

    Dest register x0, opcode JAL=0x6f. The remaining bits correspond to
    the decompressed jump immediate, with bit7 inverted from input bit15.
    """
    assert 0 <= value <= 0xFFFF_FFFF
    low = value & 0xFFFF
    assert (low & 0xE003) == 0xA001, f"not c.j: {low:04x}"
    out = 0x6F
    out |= ((low >> 12) & 1) << 31
    out |= ((low >> 8) & 1) << 30
    out |= ((low >> 9) & 3) << 28
    out |= ((low >> 6) & 1) << 27
    out |= ((low >> 7) & 1) << 26
    out |= ((low >> 2) & 1) << 25
    out |= ((low >> 11) & 1) << 24
    out |= ((low >> 3) & 7) << 21
    out |= (0x1FF if low & 0x1000 else 0) << 12
    out |= (1 ^ ((low >> 15) & 1)) << 7
    return out


async def check(dut, instruction: int) -> None:
    dut.instr_i.value = instruction
    await Timer(2, unit="ns")
    expected = expected_cj_jal(instruction)
    actual = int(dut.instr_o.value)
    assert actual == expected, (
        "PR42_CJ_VALUE_MISMATCH "
        f"input=0x{instruction:08x} expected=0x{expected:08x} "
        f"actual=0x{actual:08x} xor=0x{(actual ^ expected):08x} "
        f"bit7_diff={((actual ^ expected) >> 7) & 1}"
    )
    for name, expected_flag in (
        ("illegal_instr_o", 0),
        ("is_macro_instr_o", 0),
        ("is_compressed_o", 1),
        ("is_zcmt_instr_o", 0),
    ):
        observed = int(getattr(dut, name).value)
        assert observed == expected_flag, (
            f"PR42_CJ_FLAG_MISMATCH {name}: "
            f"input=0x{instruction:08x} expected={expected_flag} actual={observed}"
        )


@cocotb.test()
async def test_cj_directed_boundary_cases(dut):
    for payload in (0, 1, 0x7FF, 0x400, 0x200, 0x100, 0x080,
                    0x040, 0x020, 0x010, 0x008, 0x004, 0x002,
                    0x001, 0x555, 0x2AA):
        for upper in (0x0000, 0xFFFF):
            await check(dut, encode_cj(payload, upper))


@cocotb.test()
async def test_cj_all_low_16bit_encodings(dut):
    # Exactly 2^11 = 2048 possible low-halfword C.J encodings under C1/101.
    for payload in range(2048):
        await check(dut, encode_cj(payload, 0))


@cocotb.test()
async def test_cj_upper_halfword_independence(dut):
    rng = random.Random(0x42C0A6)
    for _ in range(256):
        payload = rng.randrange(2048)
        await check(dut, encode_cj(payload, rng.randrange(1 << 16)))
