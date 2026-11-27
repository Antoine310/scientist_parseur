import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def mixed_width_fixture(dut):
    dut.clk.value=0
    for data in range(256):
        dut.clk.value=0
        dut.data.value=data
        await Timer(1,unit="ns")
        dut.clk.value=1
        await Timer(1,unit="ns")
        assert int(dut.word_q.value)==((data>>5)<<1)|((data>>1)&1)
        assert int(dut.flag_q.value)==(data&1)
        assert int(dut.split_q.value)==(((data>>4)&1)<<3)|(data>>5)
