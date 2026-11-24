"""Cycle-level test against independent stack model on the real RAS."""
import random
import cocotb
from cocotb.triggers import Timer
from rtlprep.cva6_ras_reference import Entry, transition

@cocotb.test()
async def test_ras(dut):
    dut.clk_i.value = 0
    dut.rst_ni.value = 1
    dut.flush_bp_i.value = 0
    dut.push_i.value = 0
    dut.pop_i.value = 0
    dut.data_i.value = 0
    await Timer(2, unit="ns")
    dut.rst_ni.value = 0
    await Timer(2, unit="ns")
    stack = (Entry(),Entry())
    def check():
        assert int(dut.valid_o.value) == int(stack[0].valid)
        assert int(dut.ra_o.value) == stack[0].address
    check()
    dut.rst_ni.value = 1
    rng = random.Random(46)
    directed = [(1,0,0,0x12345678),(1,0,0,0x87654321),
                (1,1,0,0xABCDEF00),(0,1,0,0),(0,1,0,0),
                (1,0,1,0xFFFFFFFF)]
    vectors = directed + [(rng.randrange(2),rng.randrange(2),
                           int(rng.randrange(8)==0),rng.getrandbits(32))
                          for _ in range(256)]
    for push,pop,flush,address in vectors:
        dut.push_i.value = push
        dut.pop_i.value = pop
        dut.flush_bp_i.value = flush
        dut.data_i.value = address
        await Timer(2,unit="ns")
        check()  # no clock edge yet
        dut.clk_i.value = 1
        await Timer(2,unit="ns")
        stack = transition(stack,push=push,pop=pop,flush=flush,address=address)
        check()
        dut.clk_i.value = 0
        await Timer(2,unit="ns")
    # Assert reset with clock held low after explicitly loading a nonzero entry.
    dut.flush_bp_i.value = 0
    dut.push_i.value = 1
    dut.pop_i.value = 0
    dut.data_i.value = 0x1234
    await Timer(2,unit="ns")
    dut.clk_i.value = 1
    await Timer(2,unit="ns")
    stack = transition(stack,push=True,address=0x1234)
    check()
    dut.clk_i.value = 0
    await Timer(2,unit="ns")
    dut.rst_ni.value = 0
    await Timer(2,unit="ns")
    stack = transition(stack,reset=True)
    check()
