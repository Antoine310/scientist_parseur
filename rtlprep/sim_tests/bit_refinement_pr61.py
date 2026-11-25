import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def specialized(dut):
    for a in range(256):
        b=(a*13+3)%32
        dut.a.value=a
        dut.b.value=b
        await Timer(2,unit="ns")
        assert int(dut.x.value)==int(f"{a:08b}"[::-1],2)
        assert int(dut.y.value)==int(f"{b:05b}"[::-1],2)
        assert int(dut.lx.value)==7
        assert int(dut.ly.value)==4
