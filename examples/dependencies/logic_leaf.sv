module logic_leaf(
    input logic a,
    input logic b,
    input logic sel,
    output logic y
);
    logic and_result;
    assign and_result = a & b;
    assign y = sel ? and_result : a;
endmodule
