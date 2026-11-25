import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def functions(dut):
    # Independently vary b while holding a fixed on each group.
    for a in (0,1,0x55,0xff):
        for b in range(256):
            dut.a.value=a
            dut.b.value=b
            await Timer(2,unit="ns")
            assert int(dut.mix_o.value)==a^0x5a
            assert int(dut.both_o.value)==a^b
            assert int(dut.global_o.value)==a^b
            assert int(dut.branch_o.value)==(a if a&1 else b)
            assert int(dut.cancel_o.value)==0
