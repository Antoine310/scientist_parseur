module bitwise_pr72(
  input logic [3:0] a,b,
  input logic [1:0][3:0] p,
  output logic [3:0] y_and,y_or,y_xor,y_xnor,y_packed,y_mask,
  output logic parity
);
  assign y_and = a[3:0] & b[3:0];
  assign y_or = a[3:0] | b[3:0];
  assign y_xor = a[3:0] ^ b[3:0];
  assign y_xnor = ~(a[3:0] ^ b[3:0]);
  assign y_packed = p[1] & p[0];
  assign y_mask = a[3:0] & 4'b0000;
  assign parity = ^a[3:0];
endmodule
