import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def comparison_fixture(dut):
    dut.instr.value=0
    dut.count.value=0
    for a in range(256):
        for b in [a]+[a^(1<<j) for j in range(8)]:
            dut.a.value=a|256
            dut.b.value=b
            await Timer(1,unit="ns")
            assert int(dut.equal_byte.value)==int(a==b)
    for i in range(4):
        for count in range(4):
            dut.instr.value=i|4
            dut.count.value=count
            await Timer(1,unit="ns")
            assert int(dut.compressed.value)==int(i!=3)
            assert int(dut.full.value)==int(count==2)
