module lanes_pr57(input logic [7:0] a, input logic [2:0] idx,
    output logic [7:0] perm, output logic dynamic_o);
  for (genvar j=0; j<4; j++) begin : g
    localparam integer BASE = 2*j;
    assign perm[BASE+1:BASE] = a[7-BASE:6-BASE];
  end
  assign dynamic_o = a[idx];
endmodule
module constant_indices_pr57(input logic [7:0] a,b, input logic [2:0] idx,
    output logic [7:0] x,y, output logic dx,dy);
  lanes_pr57 u0(.a(a),.idx(idx),.perm(x),.dynamic_o(dx));
  lanes_pr57 u1(.a(b),.idx(idx),.perm(y),.dynamic_o(dy));
endmodule
