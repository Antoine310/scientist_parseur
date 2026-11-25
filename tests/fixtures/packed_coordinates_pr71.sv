module packed_coordinates_pr71(
  input logic clk,
  input logic rst_n,
  input logic [2:1][7:4] p,
  output logic [2:1][7:4] q
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      q[1] <= 4'd0;
      q[2] <= 4'd0;
    end else begin
      q[1] <= p[2];
      q[2] <= p[1];
    end
  end
endmodule
