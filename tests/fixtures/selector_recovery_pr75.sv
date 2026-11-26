module selector_recovery_pr75(
  input logic [1:0] a,b,s,
  input logic [1:0][3:0] p,q,
  output logic [1:0] y,fixed_out,
  output logic [1:0][3:0] words
);
  localparam integer N = 1;
  assign fixed_out[2**N-1] = 1'b0;
  assign fixed_out[0] = 1'b1;
  for (genvar g=0; g<2; g++) begin : gen_lane
    assign y[2**g-1] = a[g] | b[g];
    assign words[2**g-1] = s[g] ? p[g] : q[g];
  end
endmodule
