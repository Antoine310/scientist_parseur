import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def hierarchical_pipeline(dut):
    dut.clk.value=0
    dut.other_clk.value=0
    dut.data_i.value=0
    await Timer(2,unit="ns")
    for _ in range(2):
        dut.clk.value=1
        await Timer(2,unit="ns")
        dut.clk.value=0
        await Timer(2,unit="ns")
    a=b=0
    for i in range(64):
        value=(i*37+11)&255
        dut.data_i.value=value
        await Timer(2,unit="ns")
        assert int(dut.result_o.value)==b
        dut.clk.value=1
        await Timer(2,unit="ns")
        a,b=value,a
        assert int(dut.result_o.value)==b
        dut.clk.value=0
        await Timer(2,unit="ns")
        dut.other_clk.value=1
        await Timer(2,unit="ns")
        assert int(dut.cross_o.value)==b
        dut.other_clk.value=0
        await Timer(2,unit="ns")
