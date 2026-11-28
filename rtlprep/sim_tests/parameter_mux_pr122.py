import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def parameter_mux_binary_oracle(dut):
    mask=(1<<32)-1
    for b in range(32):
        for inverse in (False,True):
            a=(1<<b) ^ (mask if inverse else 0)
            other=a ^ mask
            dut.data_i.value=(other<<32)|a
            await Timer(1,unit="ns")
            assert int(dut.zero0.value)==0
            assert int(dut.zero1.value)==0
            assert int(dut.one0.value)==a
            assert int(dut.one1.value)==other
