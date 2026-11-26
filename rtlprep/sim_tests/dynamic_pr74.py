import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def indexed_read_write(dut):
    for value in range(256):
        p=(value*257)^0x5A3C
        d=value>>4
        for idx in range(4):
            dut.p.value=p
            dut.d.value=d
            dut.idx.value=idx
            await Timer(2,unit="ns")
            assert int(dut.read_bit.value)==((p>>idx)&1)
            assert int(dut.read_word.value)==((p>>(4*idx))&15)
            assert int(dut.read_unpacked.value)==((p>>(4*idx))&15)
            assert int(dut.write_word.value)==d<<(4*idx)
            assert int(dut.write_constant.value)==15<<(4*idx)
