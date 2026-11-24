import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def pipeline(dut):
    dut.clk.value=0
    dut.other_clk.value=0
    dut.en.value=1
    dut.data_i.value=0
    await Timer(2,unit="ns")
    # Warm up the unreset pipeline; no assumed initial state.
    for _ in range(3):
        dut.clk.value=1
        await Timer(2,unit="ns")
        dut.clk.value=0
        await Timer(2,unit="ns")
    q1=q2=q3=0
    for i in range(64):
        en=int(i%3!=0)
        value=(i*19+7)&255
        dut.data_i.value=value
        dut.en.value=en
        await Timer(2,unit="ns")
        assert (int(dut.q1.value),int(dut.q2.value),int(dut.q3.value))==(q1,q2,q3)
        dut.clk.value=1
        await Timer(2,unit="ns")
        q1,q2,q3=value,q1,q2 if en else q3
        assert (int(dut.q1.value),int(dut.q2.value),int(dut.q3.value))==(q1,q2,q3)
        dut.clk.value=0
        await Timer(2,unit="ns")
        dut.other_clk.value=1
        await Timer(2,unit="ns")
        assert int(dut.cross_q.value)==q3
        dut.other_clk.value=0
        await Timer(2,unit="ns")
