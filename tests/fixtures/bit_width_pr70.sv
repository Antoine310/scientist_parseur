module bit_width_pr70(
  input logic [7:0] u,
  output logic [7:0] ones,
  output logic [7:0] zeroes,
  output logic [5:0] mixed,
  output logic [2:0] flags
);
  assign ones[7:0] = '1;
  assign zeroes[7:0] = '0;
  assign mixed = {u[3:0], '1, '0};
  for (genvar k = 0; k < 3; k++) begin : gen_flag
    always_comb flags[k] = 32'd1;
  end
endmodule
