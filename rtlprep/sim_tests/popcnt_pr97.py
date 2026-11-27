"""Behavioral oracle on unchanged pinned cv32e40p_popcnt."""
import random
import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def popcount(dut):
    rng=random.Random(97)
    values=[0,0xffffffff,0xaaaaaaaa,0x55555555]+[1<<i for i in range(32)]
    values += [0xffffffff^(1<<i) for i in range(32)]
    values += [rng.getrandbits(32) for _ in range(128)]
    assert len(values)==196
    for value in values:
        dut.in_i.value=value
        await Timer(1,unit="ns")
        assert int(dut.result_o.value)==value.bit_count()
