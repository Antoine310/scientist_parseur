module signed_multiply_pr114(
    input logic [1:0][3:0] a4,b4,
    input logic [0:0][8:0] a9,b9,
    input logic [0:0][16:0] a17,b17,
    output logic [1:0][7:0] p4,
    output logic [0:0][17:0] p9,
    output logic [0:0][33:0] p17
);
    assign p4[0] = $signed(a4[0]) * $signed(b4[0]);
    assign p4[1] = $signed(a4[1]) * $signed(b4[1]);
    assign p9[0] = $signed(a9[0]) * $signed(b9[0]);
    assign p17[0] = $signed(a17[0]) * $signed(b17[0]);
endmodule
