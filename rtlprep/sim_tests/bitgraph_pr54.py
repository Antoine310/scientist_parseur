import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def lanes(dut):
    for a in range(256):
        idx=a%8
        dut.a.value=a
        dut.idx.value=idx
        await Timer(2,unit="ns")
        assert int(dut.swap_o.value)==((a&15)<<4)|(a>>4)
        assert int(dut.shifted_o.value)==((a&15)<<4)|((~a>>4)&15)
        assert int(dut.replicated_o.value)==((a&3)<<2)|(a&3)
        assert int(dut.constant_o.value)==a&15
        assert int(dut.dynamic_o.value)==(a>>idx)&1
        assert int(dut.indexed_o.value)==(a>>4)&3
        assert int(dut.array_o.value)==a
