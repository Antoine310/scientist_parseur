"""Exhaustive lower-halfword tests and deterministic upper-halfword samples."""
import random
import cocotb
from cocotb.triggers import Timer
from rtlprep.cva6_compressed_reference import FAMILIES, encode, expected

async def check(dut, word):
    ref = expected(word)
    dut.instr_i.value = word
    await Timer(2, unit="ns")
    actual = int(dut.instr_o.value)
    if ref.instruction is not None:
        assert actual == ref.instruction, (
            f"PR44_VALUE_MISMATCH family={ref.family} class={ref.classification} "
            f"input=0x{word:08x} expected=0x{ref.instruction:08x} "
            f"actual=0x{actual:08x} xor=0x{actual ^ ref.instruction:08x}"
        )
    for port, value in (("illegal_instr_o", ref.illegal), ("is_compressed_o", 1),
                        ("is_macro_instr_o", 0), ("is_zcmt_instr_o", 0)):
        assert int(getattr(dut, port).value) == value, (
            f"PR44_FLAG_MISMATCH family={ref.family} input=0x{word:08x} port={port}"
        )

async def sweep(dut, family):
    # Valid cases first, so a mutation must be observable on an ISA instruction.
    words = [encode(family, p) for p in range(2048)]
    words.sort(key=lambda w: expected(w).classification != "valid")
    for word in words:
        await check(dut, word)
    rng = random.Random(0x44C0A6 + FAMILIES[family])
    for _ in range(256):
        await check(dut, encode(family, rng.randrange(2048), rng.randrange(65536)))

@cocotb.test()
async def test_addi(dut):
    await sweep(dut, "addi")

@cocotb.test()
async def test_addi4spn(dut):
    await sweep(dut, "addi4spn")

@cocotb.test()
async def test_lw(dut):
    await sweep(dut, "lw")

@cocotb.test()
async def test_sw(dut):
    await sweep(dut, "sw")
