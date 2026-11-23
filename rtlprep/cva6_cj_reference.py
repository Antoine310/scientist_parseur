"""Independent, reviewable RV32 C.J -> JAL behavioral reference.

No imports from RTLPrep's AST, signal resolver, bit-access walker or graph.
This oracle has an intentionally narrow 2-state RISC-V c.j input domain;
it does not prove correctness of any unrelated CVA6 instruction.
"""
from __future__ import annotations


def encode_cj(payload: int, upper: int = 0) -> int:
    """Force quadrant C1, funct3=101; exactly 11 variable bits [12:2]."""
    if type(payload) is not int or not 0 <= payload < 2048:
        raise ValueError("c.j payload must be 11 bits")
    if type(upper) is not int or not 0 <= upper <= 0xFFFF:
        raise ValueError("upper halfword must be 16 bits")
    return (upper << 16) | 0xA001 | (payload << 2)


def expected_cj_jal(value: int) -> int:
    """Assemble the 32-bit JAL word independently of any RTLPrep bit metadata.

    Target x0, opcode 0x6F, jump-immediate fields, sign replication, and
    source bit15 inversion in destination bit7 as audited in pinned CVA6.
    """
    if type(value) is not int or not 0 <= value <= 0xFFFF_FFFF:
        raise ValueError("CVA6 instruction must be an unsigned 32-bit value")
    low = value & 0xFFFF
    if (low & 0xE003) != 0xA001:
        raise ValueError(f"instruction is not C.J: {low:04x}")
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
