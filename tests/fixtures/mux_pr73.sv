module mux_pr73(
  input logic [3:0] a,b,
  input logic [1:0][3:0] p,
  input logic s,t,
  output logic [3:0] y,y_nested,y_cmp,y_packed,y_const
);
  assign y = s ? a[3:0] : b[3:0];
  assign y_nested = s ? (t ? a[3:0] : b[3:0]) : '0;
  assign y_cmp = (a[0] == b[0]) ? a[3:0] : b[3:0];
  assign y_packed = s ? p[1] : p[0];
  assign y_const = t ? a[3:0] : '0;
endmodule
