"""Selected two-state behavioral checks on the genuine EX stage (FPU=0)."""
import cocotb
from cocotb.triggers import Timer

ALU_XOR=0b0101111
ALU_EQ=0b0001100
MUL_MAC32=0
MASK=(1<<32)-1
# Explicit top inputs from the pinned EX-stage source.
INPUTS="""clk rst_n alu_operator_i alu_operand_a_i alu_operand_b_i alu_operand_c_i
alu_en_i bmask_a_i bmask_b_i imm_vec_ext_i alu_vec_mode_i alu_is_clpx_i
alu_is_subrot_i alu_clpx_shift_i mult_operator_i mult_operand_a_i mult_operand_b_i
mult_operand_c_i mult_en_i mult_sel_subword_i mult_signed_mode_i mult_imm_i
mult_dot_op_a_i mult_dot_op_b_i mult_dot_op_c_i mult_dot_signed_i mult_is_clpx_i
mult_clpx_shift_i mult_clpx_img_i data_req_i data_rvalid_i data_misaligned_ex_i
data_misaligned_i ctrl_transfer_insn_in_dec_i apu_en_i apu_op_i apu_lat_i
apu_operands_i apu_waddr_i apu_flags_i apu_read_regs_i apu_read_regs_valid_i
apu_write_regs_i apu_write_regs_valid_i apu_gnt_i apu_rvalid_i apu_result_i
lsu_en_i lsu_rdata_i branch_in_ex_i regfile_alu_waddr_i regfile_alu_we_i
regfile_we_i regfile_waddr_i csr_access_i csr_rdata_i is_decoding_i
lsu_ready_ex_i lsu_err_i wb_ready_i""".split()

@cocotb.test()
async def forwarding(dut):
    for name in INPUTS:
        getattr(dut,name).value=0
    dut.alu_operator_i.value=ALU_XOR
    dut.mult_operator_i.value=MUL_MAC32
    dut.lsu_ready_ex_i.value=1
    dut.wb_ready_i.value=1
    await Timer(2,unit="ns")
    dut.clk.value=1
    await Timer(2,unit="ns")
    dut.clk.value=0
    dut.rst_n.value=1
    await Timer(2,unit="ns")
    for i in range(64):
        a=(i*0x9e3779b9)&MASK
        b=((i+3)*0x85ebca6b)&MASK
        c=(~a)&MASK
        dut.alu_operand_a_i.value=a
        dut.alu_operand_b_i.value=b
        dut.alu_operand_c_i.value=c
        dut.mult_operand_a_i.value=a
        dut.mult_operand_b_i.value=b
        dut.mult_operand_c_i.value=c
        dut.csr_rdata_i.value=b
        dut.lsu_rdata_i.value=c
        dut.alu_operator_i.value=ALU_XOR
        dut.alu_en_i.value=1
        dut.mult_en_i.value=0
        dut.csr_access_i.value=0
        dut.regfile_alu_we_i.value=1
        # XOR forwarding.
        await Timer(2,unit="ns")
        assert int(dut.regfile_alu_wdata_fw_o.value)==a^b
        assert int(dut.jump_target_o.value)==c
        assert int(dut.regfile_alu_we_fw_o.value)==1
        # Equality with both equal and unequal inputs.
        dut.alu_operator_i.value=ALU_EQ
        dut.alu_operand_b_i.value=a if i%2==0 else a^1
        await Timer(2,unit="ns")
        assert int(dut.branch_decision_o.value)==int(i%2==0)
        # Integer multiply-accumulate.
        dut.alu_en_i.value=0
        dut.mult_en_i.value=1
        await Timer(2,unit="ns")
        assert int(dut.regfile_alu_wdata_fw_o.value)==(a*b+c)&MASK
        # Both enabled: multiplier has priority over ALU in source mux.
        dut.alu_en_i.value=1
        dut.alu_operator_i.value=ALU_XOR
        await Timer(2,unit="ns")
        assert int(dut.regfile_alu_wdata_fw_o.value)==(a*b+c)&MASK
        # CSR has priority over both in the same combinational block.
        dut.csr_access_i.value=1
        await Timer(2,unit="ns")
        assert int(dut.regfile_alu_wdata_fw_o.value)==b
        # Separate LSU data output and branch-ready override.
        dut.alu_en_i.value=0
        dut.mult_en_i.value=0
        dut.csr_access_i.value=0
        dut.branch_in_ex_i.value=1
        dut.wb_ready_i.value=0
        await Timer(2,unit="ns")
        assert int(dut.regfile_wdata_wb_o.value)==c
        assert int(dut.regfile_alu_wdata_fw_o.value)==0
        assert int(dut.ex_ready_o.value)==1
        dut.branch_in_ex_i.value=0
        dut.wb_ready_i.value=1
