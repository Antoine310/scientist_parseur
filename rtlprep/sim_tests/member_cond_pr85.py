import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def configuration_values(dut):
    for data in range(4):
        for choose in range(2):
            dut.data.value=data
            dut.choose.value=choose
            await Timer(2,unit="ns")
            assert int(dut.disabled_o.value)==data
            assert int(dut.enabled_o.value)==((3 if choose else 0)<<2)|data
