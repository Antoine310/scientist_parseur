"""Independent RV32C references from the CI, CIW, CL and CS ISA formats.

No AST or RTL-derived expressions are used. Reserved encodings have no
architectural instruction result; HINT/NOP expansion is a CVA6 policy check.
"""
from dataclasses import dataclass

FAMILIES = {"addi": 0x0001, "addi4spn": 0x0000, "lw": 0x4000, "sw": 0xC000}
MASK = 0xE003

@dataclass(frozen=True)
class Expected:
    family: str
    classification: str
    instruction: int | None
    illegal: int

def encode(family: str, payload: int, upper: int = 0) -> int:
    if family not in FAMILIES or type(payload) is not int or not 0 <= payload < 2048:
        raise ValueError("invalid family or payload")
    if type(upper) is not int or not 0 <= upper < 65536:
        raise ValueError("invalid upper halfword")
    return (upper << 16) | FAMILIES[family] | (payload << 2)

def i_type(opcode, rd, funct3, rs1, imm):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def s_type(rs1, rs2, imm):
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (2 << 12) | ((imm & 31) << 7) | 0x23

def expected(word: int) -> Expected:
    if type(word) is not int or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("expected unsigned 32-bit instruction")
    h = word & 0xFFFF
    family = next((name for name, pattern in FAMILIES.items() if h & MASK == pattern), None)
    if family is None:
        raise ValueError("unsupported family")
    rd = (h >> 7) & 31
    compact = 8 + ((h >> 2) & 7)
    base = 8 + ((h >> 7) & 7)
    if family == "addi":
        imm = ((h >> 2) & 31) - 32 * ((h >> 12) & 1)
        kind = "nop" if rd == imm == 0 else "hint" if rd == 0 or imm == 0 else "valid"
        return Expected(family, kind, i_type(0x13, rd, 0, rd, imm), 0)
    if family == "addi4spn":
        imm = 4 * ((h >> 6) & 1) + 8 * ((h >> 5) & 1) + 16 * ((h >> 11) & 3) + 64 * ((h >> 7) & 15)
        return Expected(family, "valid" if imm else "reserved", i_type(0x13, compact, 0, 2, imm) if imm else None, int(imm == 0))
    offset = 4 * ((h >> 6) & 1) + 8 * ((h >> 10) & 7) + 64 * ((h >> 5) & 1)
    result = i_type(0x03, compact, 2, base, offset) if family == "lw" else s_type(base, compact, offset)
    return Expected(family, "valid", result, 0)
