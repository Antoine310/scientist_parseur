"""Behavioral tests of protected CSR writes — cocotb 2.0.1.

Reference behavior is specified independently of the implementation.
The known-bad OR mutant MUST FAIL the same test suite.
"""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer


async def reset(dut):
    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.write_i.value = 0
    dut.machine_mode_i.value = 0
    dut.debug_locked_i.value = 1
    dut.wdata_i.value = 0
    await Timer(2, unit="ns")
    assert int(dut.value_o.value) == 0, "reset must clear protected CSR"
    dut.rst_n.value = 1
    await Timer(2, unit="ns")


async def step(dut, value: int, write: int, machine: int, locked: int, data: int):
    dut.clk.value = 0
    dut.write_i.value = write
    dut.machine_mode_i.value = machine
    dut.debug_locked_i.value = locked
    dut.wdata_i.value = data
    await Timer(2, unit="ns")
    expected_accept = int(bool(write and machine and not locked))
    assert int(dut.write_accepted_o.value) == expected_accept, (
        f"authorization mismatch: write={write} machine={machine} "
        f"locked={locked}; expected={expected_accept}"
    )
    dut.clk.value = 1
    await Timer(2, unit="ns")
    expected_value = data if expected_accept else value
    assert int(dut.value_o.value) == expected_value, (
        f"protected value changed unexpectedly: expected={expected_value:02x}"
    )
    return expected_value


@cocotb.test()
async def test_unprivileged_write_is_denied_even_with_debug_unlocked(dut):
    """Critical security property: no user-mode privilege bypass."""
    await reset(dut)
    state = await step(dut, 0, 1, 0, 0, 0xA5)
    assert state == 0
    await step(dut, state, 1, 0, 1, 0x5A)


@cocotb.test()
async def test_machine_mode_write_and_lockout(dut):
    await reset(dut)
    state = await step(dut, 0, 1, 1, 0, 0x5A)
    assert state == 0x5A
    state = await step(dut, state, 1, 1, 1, 0xC3)
    assert state == 0x5A
    state = await step(dut, state, 0, 1, 0, 0x11)
    assert state == 0x5A
    # Async reset must clear even without an active clock edge.
    dut.rst_n.value = 0
    await Timer(2, unit="ns")
    assert int(dut.value_o.value) == 0


@cocotb.test()
async def test_all_access_combinations_and_deterministic_sequence(dut):
    await reset(dut)
    state = 0
    for write in (0, 1):
        for machine in (0, 1):
            for locked in (0, 1):
                state = await step(dut, state, write, machine, locked,
                                   (write * 127 + machine * 32 + locked * 11) & 255)
    rng = random.Random(0x5EC)
    for _ in range(128):
        write, machine, locked = (rng.randrange(2) for _ in range(3))
        state = await step(dut, state, write, machine, locked,
                           rng.randrange(256))
