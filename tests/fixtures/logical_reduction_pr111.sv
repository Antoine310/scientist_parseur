module logical_reduction_pr111(
    input logic a,b,c,d,
    input logic [3:0] v,
    output logic [5:0] y
);
    assign y[0] = a && !b;
    assign y[1] = !a && !b && !c;
    assign y[2] = !a && !b && !c && d;
    assign y[3] = (|v) && d;
    assign y[4] = v || b;
    assign y[5] = !v;
endmodule
