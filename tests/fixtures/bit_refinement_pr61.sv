module reverse_pr61 #(parameter W=8)(
    input logic [W-1:0] a, output logic [W-1:0] rev,
    output logic [2:0] lut_o);
  logic [W-1:0][2:0] lut;
  for (genvar k=0; k<W; k++) begin : g
    assign rev[k]=a[W-1-k];
    assign lut[k]=$unsigned(k+8);
  end
  assign lut_o=lut[W-1];
endmodule

module bit_refinement_pr61(input logic [7:0] a, input logic [4:0] b,
    output logic [7:0] x, output logic [4:0] y,
    output logic [2:0] lx,ly);
  reverse_pr61 #(.W(8)) u0(.a(a),.rev(x),.lut_o(lx));
  reverse_pr61 #(.W(5)) u1(.a(b),.rev(y),.lut_o(ly));
endmodule
