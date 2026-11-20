"""Tests cocotb de transition d'une FSM à trois états (2.0.1)."""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer

IDLE, BUSY, DONE = 0, 1, 2


async def reset(dut):
    dut.clk.value = 0
    dut.start.value = 0
    dut.ack.value = 0
    dut.rst_n.value = 0
    await Timer(2, unit="ns")
    assert int(dut.busy.value) == 0 and int(dut.done.value) == 0
    dut.rst_n.value = 1
    await Timer(2, unit="ns")


def transition(state: int, start: int, ack: int) -> int:
    """Modèle de référence explicite ; indépendant de l'implémentation RTL."""
    if state == IDLE and start:
        return BUSY
    if state == BUSY and ack:
        return DONE
    if state == DONE:
        return IDLE
    return state


async def step(dut, state: int, start: int, ack: int) -> int:
    dut.clk.value = 0
    dut.start.value = start
    dut.ack.value = ack
    await Timer(2, unit="ns")
    next_state = transition(state, start, ack)
    dut.clk.value = 1
    await Timer(2, unit="ns")
    observed = (int(dut.busy.value), int(dut.done.value))
    expected = (int(next_state == BUSY), int(next_state == DONE))
    assert observed == expected, (
        f"state={state}, start={start}, ack={ack}: attendu={expected}, observe={observed}"
    )
    return next_state


@cocotb.test()
async def test_directed_handshake(dut):
    await reset(dut)
    state = IDLE
    # Ack in IDLE ignored; START begins BUSY; START in BUSY ignored;
    # ACK finishes; DONE lasts one cycle independently of START.
    pattern = [
        (0, 1), (1, 0), (0, 0), (1, 0), (0, 1),
        (1, 1), (0, 0), (1, 1), (0, 1), (0, 0),
    ]
    for start, ack in pattern:
        state = await step(dut, state, start, ack)
    dut.rst_n.value = 0
    await Timer(2, unit="ns")
    assert int(dut.busy.value) == 0 and int(dut.done.value) == 0


@cocotb.test()
async def test_randomized_state_transitions(dut):
    await reset(dut)
    state = IDLE
    rng = random.Random(0x5EED)
    visited = {state}
    for _ in range(128):
        start = rng.randrange(2)
        ack = rng.randrange(2)
        state = await step(dut, state, start, ack)
        visited.add(state)
    assert visited == {IDLE, BUSY, DONE}, f"États non couverts : {visited}"
