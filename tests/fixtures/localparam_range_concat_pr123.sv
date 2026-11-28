module localparam_range_concat_pr123(
    input logic [31:0] instr,
    input logic regfile_fp_a,regfile_fp_b,regfile_fp_c,regfile_fp_d,
    input logic [1:0] sel,
    output logic [5:0] regfile_addr_ra_id,regfile_addr_rb_id,regfile_addr_rc_id,regfile_waddr_id
);
    localparam logic signed [31:0] REG_S1_MSB=19,REG_S1_LSB=15;
    localparam logic signed [31:0] REG_S2_MSB=24,REG_S2_LSB=20;
    localparam logic signed [31:0] REG_D_MSB=11,REG_D_LSB=7;
    localparam logic signed [31:0] REG_S4_MSB=31,REG_S4_LSB=27;
    assign regfile_addr_ra_id={regfile_fp_a,instr[REG_S1_MSB:REG_S1_LSB]};
    assign regfile_addr_rb_id={regfile_fp_b,instr[REG_S2_MSB:REG_S2_LSB]};
    always_comb begin
        case (sel)
            2'd0: regfile_addr_rc_id={regfile_fp_c,instr[REG_D_MSB:REG_D_LSB]};
            2'd1: regfile_addr_rc_id={regfile_fp_c,instr[REG_S1_MSB:REG_S1_LSB]};
            2'd2: regfile_addr_rc_id={regfile_fp_c,instr[REG_S4_MSB:REG_S4_LSB]};
            default: regfile_addr_rc_id=6'd0;
        endcase
    end
    assign regfile_waddr_id={regfile_fp_d,instr[REG_D_MSB:REG_D_LSB]};
endmodule
