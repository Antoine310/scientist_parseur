module packed_lane_concat_pr121(
    input logic mode,
    input logic [1:0] imm_vec_ext_i,
    input logic [31:0] operand_b_i,
    output logic [3:0][1:0] shuffle_byte_sel
);
    always_comb begin
        if (mode) begin
            shuffle_byte_sel[3] = {imm_vec_ext_i[0],1'b1};
            shuffle_byte_sel[2] = {imm_vec_ext_i[0],1'b1};
            shuffle_byte_sel[1] = {imm_vec_ext_i[0],1'b1};
            shuffle_byte_sel[0] = {imm_vec_ext_i[0],1'b0};
        end else begin
            shuffle_byte_sel[3] = {operand_b_i[16],1'b1};
            shuffle_byte_sel[2] = {operand_b_i[16],1'b0};
            shuffle_byte_sel[1] = {operand_b_i[0],1'b1};
            shuffle_byte_sel[0] = {operand_b_i[0],1'b0};
        end
    end
endmodule
