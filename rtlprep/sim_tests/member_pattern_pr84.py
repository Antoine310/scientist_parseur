import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def sampled_pattern(dut):
    dut.clk.value=0
    dut.choose.value=0
    dut.data.value=0
    await Timer(2,unit="ns")
    dut.clk.value=1
    await Timer(2,unit="ns")
    previous=4
    assert int(dut.readback.value)==previous
    for v in range(32):
        choose=v&1
        dut.clk.value=0
        dut.data.value=v
        dut.choose.value=choose
        await Timer(2,unit="ns")
        assert int(dut.readback.value)==((choose<<7)|previous)
        dut.clk.value=1
        await Timer(2,unit="ns")
        previous=(v&24)|4
        assert int(dut.readback.value)==((choose<<7)|previous)
