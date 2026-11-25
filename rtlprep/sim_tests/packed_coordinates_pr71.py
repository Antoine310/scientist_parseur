import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def fixed_word_swap(dut):
    dut.clk.value=0
    dut.rst_n.value=0
    dut.p.value=255
    await Timer(2,unit="ns")
    dut.clk.value=1
    await Timer(2,unit="ns")
    assert int(dut.q.value)==0
    dut.rst_n.value=1
    for value in range(256):
        dut.clk.value=0
        dut.p.value=value
        await Timer(2,unit="ns")
        dut.clk.value=1
        await Timer(2,unit="ns")
        assert int(dut.q.value)==((value&15)<<4)|(value>>4)
