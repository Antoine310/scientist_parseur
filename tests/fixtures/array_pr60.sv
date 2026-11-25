module array_pr60(input logic [7:0] a,b, input logic [1:0] idx,
    output logic [7:0] word_o,dynamic_o,grid_o,
    output logic [3:0] slice_o,packed_o,
    output logic bit_o);
  logic [7:0] arr [1:2];
  logic [1:0][7:0] packed_arr;
  logic [7:0] grid [2:1][0:1];
  assign arr[1]=a;
  assign arr[2]=b;
  assign word_o=arr[1];
  assign slice_o=arr[2][5:2];
  assign bit_o=arr[1][7];
  assign dynamic_o=arr[idx];
  assign packed_arr[0]=b;
  assign packed_arr[1]=a;
  assign packed_o=packed_arr[0][3:0];
  assign grid[2][0]=a;
  assign grid_o=grid[2][0];
endmodule
