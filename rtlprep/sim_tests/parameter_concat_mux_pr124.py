import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def parameter_concat_mux_binary_oracle(dut):
    for frm in range(8):
        for flags in range(32):
            dut.frm_q.value=frm
            dut.fflags_q.value=flags
            await Timer(1,unit="ns")
            assert int(dut.flags0.value)==0
            assert int(dut.frm0.value)==0
            assert int(dut.fcsr0.value)==0
            assert int(dut.flags1.value)==flags
            assert int(dut.frm1.value)==frm
            assert int(dut.fcsr1.value)==32*frm+flags
