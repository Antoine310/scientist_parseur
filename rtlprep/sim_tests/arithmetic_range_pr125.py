import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def arithmetic_range_binary_oracle(dut):
    # Exhaust the low byte; independently vary every upper bit and its complement.
    noise=[0,0xffffff00]+[1<<k for k in range(8,32)]+[0xffffff00^(1<<k) for k in range(8,32)]
    for low in range(256):
        for high in noise:
            for sel in range(4):
                dut.csr_wdata_int.value=high|low
                dut.sel.value=sel
                await Timer(1,unit="ns")
                assert int(dut.fflags_n.value)==(low&31 if sel in (0,2) else 0)
                assert int(dut.frm_n.value)==(low&7 if sel==1 else (low>>5)&7 if sel==2 else 0)
