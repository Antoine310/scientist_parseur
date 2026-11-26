import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def scalar_field_writes(dut):
    for v in range(16):
        dut.data.value = v
        await Timer(2, unit="ns")
        assert int(dut.packed_o.value) == ((v & 8) | (v & 2) | 1)
