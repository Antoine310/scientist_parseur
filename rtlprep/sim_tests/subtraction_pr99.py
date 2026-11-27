import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def subtraction_and_mask(dut):
    for a in range(4):
        for b in range(4):
            dut.a.value=a|4
            dut.b.value=b|4
            await Timer(1,unit="ns")
            assert int(dut.delta.value)==(a-b)%4
    for k in range(32):
        dut.instr.value=(k<<2)|0x83
        await Timer(1,unit="ns")
        assert int(dut.mask.value)==(1<<k)-1
