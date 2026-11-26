import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def field_positions(dut):
    for v in range(256):
        dut.high_i.value = v >> 5
        dut.low_i.value = v & 31
        await Timer(2, unit="ns")
        assert int(dut.high_o.value) == v >> 5
        assert int(dut.low_o.value) == v & 31
        assert int(dut.packed_o.value) == v
