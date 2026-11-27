module signed_order_pr101(
    input logic [8:0] a,b,
    input logic [1:0] mode,
    output logic [0:0] greater
);
    assign greater[0] = $signed({a[7] & mode[0], a[7:0]}) >
                     $signed({b[7] & mode[0], b[7:0]});
endmodule
