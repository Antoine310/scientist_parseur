"""Banc de test comportemental du compteur 8 bits, cocotb 2.0.1.

Chaque test dispose de son propre reset. Une comparaison avec une
référence Python valide les sorties *après* chaque front d'horloge.
"""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer


async def reset(dut):
    dut.clk.value = 0
    dut.enable.value = 0
    dut.rst_n.value = 0
    await Timer(2, unit="ns")
    assert int(dut.count.value) == 0, "Reset asynchrone doit effacer count"
    dut.rst_n.value = 1
    await Timer(2, unit="ns")


async def cycle(dut, enable: int, expected: int):
    dut.clk.value = 0
    dut.enable.value = enable
    await Timer(2, unit="ns")
    dut.clk.value = 1
    await Timer(2, unit="ns")
    observed = int(dut.count.value)
    assert observed == expected, (
        f"enable={enable} : count attendu={expected}, observe={observed}"
    )


@cocotb.test()
async def test_enable_and_hold(dut):
    """Incrémenter seulement lorsque enable=1, maintenir si enable=0."""
    await reset(dut)
    count = 0
    pattern = [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1]
    for enabled in pattern:
        count = (count + enabled) & 0xFF
        await cycle(dut, enabled, count)


@cocotb.test()
async def test_wraparound(dut):
    """Un registre 8 bits revient à zéro après 256 incréments."""
    await reset(dut)
    for value in range(1, 260):
        await cycle(dut, 1, value & 0xFF)


@cocotb.test()
async def test_async_reset_and_deterministic_stimuli(dut):
    """Reset hors front d'horloge et 128 stimuli pseudo-aléatoires reproductibles."""
    await reset(dut)
    expected = 0
    rng = random.Random(0xC0FFEE)
    for _ in range(128):
        enabled = rng.randrange(2)
        expected = (expected + enabled) & 0xFF
        await cycle(dut, enabled, expected)
    # L'horloge est encore à l'état haut : vérifier reset sans front montant.
    dut.rst_n.value = 0
    await Timer(2, unit="ns")
    assert int(dut.count.value) == 0, "Reset asynchrone ignoré hors front"
    dut.clk.value = 0
    dut.enable.value = 0
    await Timer(2, unit="ns")
    dut.rst_n.value = 1
    await Timer(2, unit="ns")
    await cycle(dut, 0, 0)
