"""Directed counterexamples to distinct RAS priority mutations."""
import cocotb
from cocotb.triggers import Timer
from rtlprep.cva6_ras_reference import Entry, transition

async def exercise(dut, scenario, vectors):
    for key in ("clk_i","flush_bp_i","push_i","pop_i","data_i"):
        getattr(dut,key).value=0
    dut.rst_ni.value=1
    await Timer(2,unit="ns")
    dut.rst_ni.value=0
    await Timer(2,unit="ns")
    dut.rst_ni.value=1
    stack=(Entry(),Entry())
    for i,(push,pop,flush,address) in enumerate(vectors):
        dut.push_i.value=push
        dut.pop_i.value=pop
        dut.flush_bp_i.value=flush
        dut.data_i.value=address
        await Timer(2,unit="ns")
        dut.clk_i.value=1
        await Timer(2,unit="ns")
        stack=transition(stack,push=push,pop=pop,flush=flush,address=address)
        want=(int(stack[0].valid),stack[0].address)
        got=(int(dut.valid_o.value),int(dut.ra_o.value))
        assert got==want, f"PR47_RAS_MISMATCH scenario={scenario} cycle={i} expected={want} actual={got}"
        dut.clk_i.value=0
        await Timer(2,unit="ns")

@cocotb.test()
async def simultaneous(dut):
    await exercise(dut,"simultaneous",[(1,0,0,17),(1,0,0,34),(1,1,0,51),(0,1,0,0)])

@cocotb.test()
async def flush_priority(dut):
    await exercise(dut,"flush_priority",[(1,0,0,17),(1,0,1,34),(0,1,0,0)])
