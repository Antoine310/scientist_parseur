import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def enum_conversion_oracle(dut):
    for word in range(256):
        sel=word&1
        dut.sel.value=sel
        dut.word.value=word
        await Timer(1,unit="ns")
        assert int(dut.op.value)==sel
        assert int(dut.fmt.value)==(5 if sel else 2)
        assert int(dut.state.value)==(word>>3)&3
