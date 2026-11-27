module shift_candidates_pr112(
    input logic [7:0] d,
    input logic [4:0] k,
    output logic [7:0] fixed_o,left_o,
    output logic [3:0] right_o,
    output logic [31:0] mask_o
);
    assign fixed_o[7:0] = d << 2;
    assign left_o[7:0] = d << k[2:0];
    assign right_o[3:0] = d >> k[2:0];
    assign mask_o[31:0] = {32'hfffffffe} << k;
endmodule
