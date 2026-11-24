// Full-width reset/enable priority regression, separate from real CVA6.
module reset_formal_pr48(input wire clk, rst_n, enable, input wire [7:0] d,
                        output reg [7:0] q);
  always @(posedge clk or negedge rst_n)
    if (!rst_n) q <= 0;
    else if (enable) q <= d;
endmodule
