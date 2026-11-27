module subtraction_pr99(
    input logic [2:0] a,b,
    input logic [7:0] instr,
    output logic [1:0] delta,
    output logic [31:0] mask
);
    assign delta = a[1:0] - b[1:0];
    assign mask = (32'd1 << instr[6:2]) - 32'd1;
endmodule
