import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def localparam_concat_oracle(dut):
    for k in range(32):
        for inverse in (0,1):
            instr=(1<<k) ^ (0xffffffff if inverse else 0)
            for flags in range(16):
                for sel in range(4):
                    dut.instr.value=instr
                    dut.regfile_fp_a.value=flags&1
                    dut.regfile_fp_b.value=(flags>>1)&1
                    dut.regfile_fp_c.value=(flags>>2)&1
                    dut.regfile_fp_d.value=(flags>>3)&1
                    dut.sel.value=sel
                    await Timer(1,unit="ns")
                    assert int(dut.regfile_addr_ra_id.value)==((flags&1)*32+(instr>>15&31))
                    assert int(dut.regfile_addr_rb_id.value)==(((flags>>1)&1)*32+(instr>>20&31))
                    assert int(dut.regfile_addr_rc_id.value)==(0 if sel==3 else (((flags>>2)&1)*32+(instr>>(7,15,27)[sel]&31)))
                    assert int(dut.regfile_waddr_id.value)==(((flags>>3)&1)*32+(instr>>7&31))
