import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def member_expressions(dut):
    for data in range(8):
        for extra in range(4):
            dut.data.value = data
            dut.extra.value = extra
            await Timer(2, unit="ns")
            a,b,c = (data>>2)&1,(data>>1)&1,data&1
            assert int(dut.flag.value) == int(bool(a and not (b and not c)))
            assert int(dut.readback.value) == ((a<<4)|(extra<<2)|(b<<1)|c)
