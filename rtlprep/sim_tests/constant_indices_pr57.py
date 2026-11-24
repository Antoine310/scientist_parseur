import cocotb
from cocotb.triggers import Timer

def reverse_pairs(value):
    return sum(((value>>(2*i))&3)<<(2*(3-i)) for i in range(4))

@cocotb.test()
async def pairs(dut):
    for a in range(256):
        b=(a*73+11)%256
        idx=a%8
        dut.a.value=a
        dut.b.value=b
        dut.idx.value=idx
        await Timer(2,unit="ns")
        assert int(dut.x.value)==reverse_pairs(a)
        assert int(dut.y.value)==reverse_pairs(b)
        assert int(dut.dx.value)==(a>>idx)&1
        assert int(dut.dy.value)==(b>>idx)&1
