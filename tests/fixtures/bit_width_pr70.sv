module bit_width_pr70(
  input logic [7:0] u,
  output logic [7:0] ones,
  output logic [7:0] zeroes,
  output logic [5:0] mixed
);
  assign ones[7:0] = '1;
  assign zeroes[7:0] = '0;
  assign mixed = {u[3:0], '1, '0};
endmodule
