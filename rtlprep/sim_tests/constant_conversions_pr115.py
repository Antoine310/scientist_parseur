import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def constant_conversion_oracle(dut):
    for d in (0,1,0x8000,0xffff):
        dut.d.value=d
        await Timer(1,unit="ns")
        counters=int(dut.counter_q.value)
        events=int(dut.event_q.value)
        lut=int(dut.index_lut.value)
        for j in range(4):
            assert (counters>>(64*j))&((1<<64)-1)==0
            assert (lut>>(5*j))&31==j
            assert (events>>(32*j))&0xffffffff==(d if j==3 else 0)
