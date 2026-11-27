module dynamic_conversions_pr116(
    input logic [3:0] u,
    input logic signed [3:0] s,
    input logic [7:0] wide,
    output logic [7:0] z,
    output logic signed [7:0] ext,
    output logic [3:0] trunc
);
    always_comb z = u;
    assign ext = s;
    assign trunc = wide;
endmodule
