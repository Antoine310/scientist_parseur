module hierarchy_stage52(input logic clk, input logic [7:0] d, output logic [7:0] q);
  always_ff @(posedge clk) q <= d;
endmodule
module hierarchy_pair52(input logic clk, input logic [7:0] d, output logic [7:0] q);
  logic [7:0] mid;
  hierarchy_stage52 a(.clk(clk), .d(d), .q(mid));
  hierarchy_stage52 b(.clk(clk), .d(mid), .q(q));
endmodule
module hierarchy_pr52(input logic clk, other_clk, input logic [7:0] data_i,
  output logic [7:0] result_o, cross_o);
  hierarchy_pair52 pair_i(.clk(clk), .d(data_i), .q(result_o));
  hierarchy_stage52 cross_i(.clk(other_clk), .d(result_o), .q(cross_o));
endmodule
