module bitgraph_pr54(input logic [7:0] a, input logic [2:0] idx,
    output logic [7:0] swap_o, constant_o, array_o,
    output logic [11:4] shifted_o,
    output logic [3:0] replicated_o,
    output logic [1:0] indexed_o,
    output logic dynamic_o);
  logic [7:0] arr [0:1];
  assign swap_o = {a[3:0],a[7:4]};
  assign shifted_o[11:8] = a[3:0];
  assign shifted_o[7:4] = ~a[7:4];
  assign replicated_o = {2{a[1:0]}};
  assign constant_o = {4'b0,a[3:0]};
  assign dynamic_o = a[idx];
  assign indexed_o = a[4 +: 2];
  assign arr[0] = a;
  assign arr[1] = ~a;
  assign array_o = arr[0];
endmodule
