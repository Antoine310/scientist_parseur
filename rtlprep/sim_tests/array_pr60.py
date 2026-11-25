import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def arrays(dut):
    for a in range(256):
        b=(73*a+11)%256
        for idx in (1,2):
            dut.a.value=a
            dut.b.value=b
            dut.idx.value=idx
            await Timer(2,unit="ns")
            assert int(dut.word_o.value)==a
            assert int(dut.slice_o.value)==(b>>2)&15
            assert int(dut.bit_o.value)==(a>>7)&1
            assert int(dut.dynamic_o.value)==(a if idx==1 else b)
            assert int(dut.packed_o.value)==b&15
            assert int(dut.grid_o.value)==a
