"""Allowlisted training fixture for hardware-security regression testing.

No arbitrary user-supplied RTL may be sent through the new lab's approved
simulation/formal suites merely by claiming the "secure_csr" module name.
"""
from __future__ import annotations

from pathlib import Path

from .manifest import Design

LAB_ROOT = Path(__file__).resolve().parent.parent / "examples" / "security_csr"
LAB_SOURCES = frozenset({
    "secure_csr.sv", "secure_csr_buggy.sv", "secure_csr_refactored.sv",
})


def validate_security_design(d: Design) -> None:
    """Reject spoofed top names, paths or extra sources/options."""
    if d.top != "secure_csr":
        raise ValueError("Le banc de sécurité attend secure_csr")
    if len(d.sources) != 1 or d.includes or d.defines:
        raise ValueError("Banc de sécurité : une source approuvée, sans options")
    if not any(d.sources[0].resolve() == (LAB_ROOT / name).resolve()
               for name in LAB_SOURCES):
        raise ValueError("Source RTL du laboratoire non approuvée")
