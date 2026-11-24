// Full-width same-process NBA priority; deliberately distinct from RAS blocking writes.
module nba_priority_pr47(input logic clk, rst_n, en_a, en_b,
  input logic [7:0] a,b, output logic [7:0] q);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) q <= 8'd0;
    else begin
      if (en_a) q <= a;
      if (en_b) q <= b;
    end
  end
endmodule
