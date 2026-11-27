module state_conversions_pr118(
    input logic [1:0] src4,
    input bit [1:0] src2,
    output bit [1:0] dst2,
    output logic [1:0] dst4
);
    always_comb begin
        dst2 = src4;
        dst4 = src2;
    end
endmodule
