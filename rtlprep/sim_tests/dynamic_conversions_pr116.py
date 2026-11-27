import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def dynamic_conversion_oracle(dut):
    for x in range(256):
        u=x&15
        dut.u.value=u
        dut.s.value=u if u<8 else u-16
        dut.wide.value=x
        await Timer(1,unit="ns")
        assert int(dut.z.value)==u
        assert int(dut.ext.value)&255==((u if u<8 else u-16)&255)
        assert int(dut.trunc.value)==x%16
