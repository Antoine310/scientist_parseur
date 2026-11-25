import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def exhaustive_input_values(dut):
    for value in range(256):
        dut.u.value=value
        # Two's complement bit pattern; drive signed port using signed value.
        dut.s.value=value if value<128 else value-256
        await Timer(2,unit="ns")
        assert int(dut.zext.value)==value
        assert int(dut.sext.value)==(value | (0xf00 if value&0x80 else 0))
        assert int(dut.narrowed.value)==value&15
