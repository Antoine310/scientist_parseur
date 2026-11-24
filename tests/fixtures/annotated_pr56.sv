module annotated_pr56(input logic clk, en,
    input logic [7:0] a, b,
    input logic [2:0] idx,
    output logic [7:0] swap_o, inv_o, mix_o, call_o, q,
    output logic bit_o);
  assign swap_o = {a[3:0], a[7:4]};
  assign inv_o = {~b[7:4], b[3:0]};
  assign mix_o = en ? a : b;
  function automatic logic [7:0] f(input logic [7:0] x, unused);
    return x ^ 8'h5a;
  endfunction
  assign call_o = f(a, b);
  assign bit_o = a[idx];
  always_ff @(posedge clk)
    if (en) q <= a;
endmodule
