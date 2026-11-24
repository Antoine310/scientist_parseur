"""Cocotb checks on official, pinned CVA6 compressed_decoder: C.LI and HINTs.

Independent expected 32-bit ADDI construction lives in the pure
rtlprep.cva6_cli_reference module, never in RTLPrep's AST or graph.
"""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer

from rtlprep.cva6_cli_reference import (
    cli_encoding_class, encode_cli, expected_cli_addi,
)


async def check(dut, instruction: int) -> None:
    dut.instr_i.value = instruction
    await Timer(2, unit="ns")
    expected = expected_cli_addi(instruction)
    actual = int(dut.instr_o.value)
    difference = actual ^ expected
    assert actual == expected, (
        "PR43_CLI_VALUE_MISMATCH "
        f"class={cli_encoding_class(instruction)} "
        f"input=0x{instruction:08x} expected=0x{expected:08x} "
        f"actual=0x{actual:08x} xor=0x{difference:08x} "
        f"bit24_diff={(difference >> 24) & 1}"
    )
    # Flags are deliberately tested on *both* legitimate C.LI and rd=x0 HINT
    # encodings as observed behavior of this exact decoder/configuration.
    for name, expected_flag in (
        ("illegal_instr_o", 0),
        ("is_macro_instr_o", 0),
        ("is_compressed_o", 1),
        ("is_zcmt_instr_o", 0),
    ):
        observed = int(getattr(dut, name).value)
        assert observed == expected_flag, (
            "PR43_CLI_FLAG_MISMATCH "
            f"class={cli_encoding_class(instruction)} "
            f"port={name} input=0x{instruction:08x} "
            f"expected={expected_flag} actual={observed}"
        )


@cocotb.test()
async def test_cli_directed_sign_register_and_imm_cases(dut):
    # 16 distinct payloads, each with upper halfword zero and all ones.
    for payload in (
        0, 1, 0x7FF, 0x400, 0x200, 0x100, 0x080, 0x040,
        0x020, 0x010, 0x008, 0x004, 0x002, 0x001, 0x555, 0x2AA,
    ):
        for upper in (0, 0xFFFF):
            await check(dut, encode_cli(payload, upper))


@cocotb.test()
async def test_cli_all_2048_lower_halfword_patterns(dut):
    # 1984 defined C.LI instructions + 64 rd=x0 HINT encodings.
    # Exact sweep in this 16-bit family with *upper halfword zero*.
    for payload in range(2048):
        await check(dut, encode_cli(payload))


@cocotb.test()
async def test_cli_upper_halfword_independence(dut):
    rng = random.Random(0x43C0A6)
    for _ in range(256):
        payload = rng.randrange(2048)
        await check(dut, encode_cli(payload, rng.randrange(1 << 16)))
