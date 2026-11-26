import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def packed_positions(dut):
    for data in range(4096):
        dut.data.value = data
        await Timer(2, unit="ns")
        assert int(dut.hi.value) == data >> 4
        assert int(dut.lo.value) == data & 15
        assert int(dut.zero_o.value) == 0
