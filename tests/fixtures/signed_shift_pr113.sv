module signed_shift_pr113(
    input logic [7:0] d,
    input logic [2:0] k,
    input logic mode,
    output logic [7:0] y8,
    output logic [7:4] y4
);
    assign y8[7:0] = $signed({mode & d[7], d[7:0]}) >>> k[2:0];
    assign y4[7:4] = $signed({mode & d[7], d[7:4]}) >>> k[1:0];
endmodule
