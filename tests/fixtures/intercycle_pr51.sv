module intercycle_pr51(input logic clk, other_clk, en,
    input logic [7:0] data_i, output logic [7:0] q1,q2,q3,cross_q);
  always_ff @(posedge clk) begin
    q1 <= data_i;
    q2 <= q1;
    if (en) q3 <= q2;
  end
  always_ff @(posedge other_clk) cross_q <= q3;
endmodule
