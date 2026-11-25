module bit_width_pr69(
  input logic [7:0] u,
  input logic signed [7:0] s,
  output logic [11:0] zext,
  output logic [11:0] sext,
  output logic [3:0] narrowed
);
  assign zext = {12'(u)};
  assign sext = {12'(s)};
  assign narrowed = {4'(u)};
endmodule
