import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def binary_state_conversion_oracle(dut):
    for a in range(4):
        for b in range(4):
            dut.src4.value=a
            dut.src2.value=b
            await Timer(1,unit="ns")
            assert int(dut.dst2.value)==a
            assert int(dut.dst4.value)==b
