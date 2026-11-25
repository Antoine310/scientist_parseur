import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def exhaustive_truth_tables(dut):
    for a in range(16):
        for b in range(16):
            dut.a.value=a
            dut.b.value=b
            dut.p.value=(a<<4)|b
            await Timer(2,unit="ns")
            assert int(dut.y_and.value)==a&b
            assert int(dut.y_or.value)==a|b
            assert int(dut.y_xor.value)==a^b
            assert int(dut.y_xnor.value)==(~(a^b))&15
            assert int(dut.y_packed.value)==a&b
            assert int(dut.y_mask.value)==0
            assert int(dut.parity.value)==a.bit_count()%2
