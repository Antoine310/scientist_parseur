module complex_pr53(input logic [7:0] a,b,c,d, input logic [1:0] idx,
  output logic [7:0] call_o, literal_o, dynamic_o, repeat_o,
  output logic [9:0] sum_o);
  logic [7:0] arr [0:3];
  assign arr[0]=a;
  assign arr[1]=b;
  assign arr[2]=c;
  assign arr[3]=d;
  function automatic logic [7:0] mix(input logic [7:0] x, unused);
    return x ^ 8'h5a;
  endfunction
  assign call_o=mix(a,b);
  assign literal_o=arr[2];
  assign dynamic_o=arr[idx];
  always_comb begin
    repeat_o=a;
    repeat (3) repeat_o=repeat_o+8'd1;
  end
  always_comb begin
    sum_o=10'd0;
    for (int i=0; i<4; i++)
      sum_o=sum_o+{2'b0,arr[i]};
  end
endmodule
