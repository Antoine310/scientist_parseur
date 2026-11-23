// RTLPrep-owned input to real slang v12.1 regression. No simulation oracle.
module unary_bit_pr40 (
    input  logic [15:0] instr_i,
    input  logic        en,
    output logic        bit_o,
    output logic [7:0]  mix_o,
    output logic [3:0]  wide_o,
    output logic [7:0]  logical_o,
    output logic [3:0]  reduction_o
);
  always_comb begin
    bit_o = ~instr_i[15];
    mix_o = {instr_i[7:5], ~instr_i[4], instr_i[3:0]};
    wide_o = ~instr_i[3:0];
    if (en) begin
      logical_o   = {7'b0, !instr_i[3]};
      reduction_o = {3'b0, &instr_i[7:4]};
    end else begin
      logical_o   = 8'b0;
      reduction_o = 4'b0;
    end
  end
endmodule
