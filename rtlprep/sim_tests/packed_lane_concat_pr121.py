import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def packed_lane_binary_oracle(dut):
    # Exhaust all distinct observed bits, mode and unused immediate bit;
    # toggle every other operand bit together as an independence check.
    for mode in range(2):
        for imm in range(4):
            for a in range(2):
                for b in range(2):
                    for noise in (0,0xfffefffe):
                        word=noise | (a<<16) | b
                        dut.mode.value=mode
                        dut.imm_vec_ext_i.value=imm
                        dut.operand_b_i.value=word
                        await Timer(1,unit="ns")
                        expected=(0x54 | (0xaa if imm&1 else 0)) if mode else (0x44 | (0xa0 if a else 0) | (0x0a if b else 0))
                        assert int(dut.shuffle_byte_sel.value)==expected
