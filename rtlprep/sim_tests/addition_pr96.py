import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def independent_modular_addition(dut):
    for a in range(16):
        for b in range(16):
            dut.a.value=a|0xA0
            dut.b.value=b|0x50
            await Timer(1,unit="ns")
            assert int(dut.sum4.value)==(a+b)%16
    for x,y in [(0,0),(1,1),(0xffffffff,1),(0x7fffffff,1),
                (0xaaaaaaaa,0x55555555),(0xffffffff,0xffffffff),
                (0x12345678,0x87654321),(0x80000000,0x80000000)]:
        dut.x.value=x|(1<<32)
        dut.y.value=y|(1<<32)
        await Timer(1,unit="ns")
        assert int(dut.sum32.value)==(x+y)%(1<<32)
