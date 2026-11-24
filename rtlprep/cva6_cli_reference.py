"""Independent RV32 C.LI -> ADDI behavior reference for an audited CVA6 branch.

Derives its meaning from the RISC-V compressed CI instruction format, NOT
from slang's AST, RTLPrep bit_accesses, graph, or the CVA6 implementation.

C.LI requires rd != x0 in the ISA. The 64 patterns with rd == x0 are
HINTs; the CVA6 decoder's observable conversion of those encodings is
tested as an IMPLEMENTATION observation, not a claim of ISA-valid C.LI.
All tests are 2-state and confined to the C1/funct3=010 encoding family.
"""
from __future__ import annotations


def encode_cli(payload: int, upper: int = 0) -> int:
    """Build low halfword with funct3=010 and quadrant=01, 11 variable bits."""
    if type(payload) is not int or not 0 <= payload < 2048:
        raise ValueError("C.LI payload must contain 11 bits")
    if type(upper) is not int or not 0 <= upper <= 0xFFFF:
        raise ValueError("upper halfword must contain 16 bits")
    return (upper << 16) | 0x4001 | (payload << 2)


def cli_encoding_class(instruction: int) -> str:
    """Distinguish the ISA-defined C.LI domain from rd=x0 HINT encodings."""
    _require_cli(instruction)
    return "hint_rd_zero" if ((instruction >> 7) & 0x1F) == 0 else "valid_cli"


def _require_cli(instruction: int) -> int:
    if type(instruction) is not int or not 0 <= instruction <= 0xFFFF_FFFF:
        raise ValueError("CVA6 instruction must be a 32-bit unsigned integer")
    low = instruction & 0xFFFF
    if (low & 0xE003) != 0x4001:
        raise ValueError("instruction is not in the C.LI encoding family")
    return low


def expected_cli_addi(instruction: int) -> int:
    """Construct ADDI rd,x0,sign_extended_imm6 as an independent integer model.

    RVC CI fields: imm[5] from bit12, imm[4:0] from bits6:2, rd
    from bits11:7. RV32I opcode=0x13, funct3=0, rs1=x0.
    For rd=x0 HINTs, this models the observed CVA6 decode policy only.
    """
    half = _require_cli(instruction)
    destination = (half >> 7) & 0x1F
    immediate = ((half >> 2) & 0x1F) + (((half >> 12) & 1) * 32)
    signed_immediate = immediate - 64 if immediate >= 32 else immediate
    encoded_imm12 = signed_immediate & 0xFFF
    return (encoded_imm12 << 20) | (destination << 7) | 0x13
