import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def loops(dut):
    for a in range(256):
        for count in (0,1,7):
            dut.a.value=a
            dut.count_i.value=count
            await Timer(2,unit="ns")
            assert int(dut.reverse_o.value)==int(f"{a:08b}"[::-1],2)
            assert int(dut.identity_o.value)==a
            assert int(dut.repeat_o.value)==(a&1)
            assert int(dut.dynamic_o.value)==((a>>1)&1 if count else 0)
            assert int(dut.limited_o.value)==((a>>2)&1)
