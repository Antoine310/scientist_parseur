module addition_pr96(
    input logic [7:0] a,b,
    input logic [32:0] x,y,
    output logic [3:0] sum4,
    output logic [31:0] sum32
);
    assign sum4 = a[3:0] + b[3:0];
    assign sum32 = x[31:0] + y[31:0];
endmodule
