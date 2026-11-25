module static_loops_pr59(input logic [7:0] a, input logic [2:0] count_i,
    output logic [7:0] reverse_o, identity_o,
    output logic repeat_o, dynamic_o, limited_o);
  always_comb begin
    for (int i=0; i<8; i++)
      reverse_o[i] = a[7-i];
  end
  always_comb begin
    for (int j=0; j<=7; ++j)
      identity_o[j] = a[j];
  end
  always_comb begin
    repeat (3) repeat_o = a[0];
  end
  always_comb begin
    dynamic_o = 1'b0;
    repeat (count_i) dynamic_o = a[1];
  end
  always_comb begin
    repeat (65) limited_o = a[2];
  end
endmodule
