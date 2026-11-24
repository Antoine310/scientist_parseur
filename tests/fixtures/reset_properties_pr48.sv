module reset_properties_pr48(input wire clk, rst_n, enable, input wire [7:0] d);
  wire [7:0] q;
  reset_formal_pr48 dut(clk,rst_n,enable,d,q);
  reg [7:0] ref_q;
  reg initialized=0;
  initial assume(!rst_n);
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin ref_q<=0; initialized<=1; end
    else if (enable) ref_q<=d;
  always @(*) if(initialized) assert(q==ref_q);
  always @(posedge clk) if(initialized && rst_n) cover(q!=0 && !enable);
endmodule
