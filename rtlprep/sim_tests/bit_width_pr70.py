import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def literal_fill_and_concat(dut):
    for value in range(256):
        dut.u.value=value
        await Timer(2,unit="ns")
        assert int(dut.ones.value)==255
        assert int(dut.zeroes.value)==0
        assert int(dut.mixed.value)==((value&15)<<2)|2
