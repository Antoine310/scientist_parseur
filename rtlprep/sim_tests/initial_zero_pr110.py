import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def startup_then_updates(dut):
    dut.clk.value=0
    dut.data.value=0
    await Timer(1,unit="ns")
    assert int(dut.flag_q.value)==0
    assert int(dut.word_q.value)==0
    assert int(dut.byte_q.value)==0
    for data in range(256):
        dut.clk.value=0
        dut.data.value=data
        await Timer(1,unit="ns")
        dut.clk.value=1
        await Timer(1,unit="ns")
        assert int(dut.flag_q.value)==(data&1)
        assert int(dut.word_q.value)==(data>>4)
        assert int(dut.byte_q.value)==data
