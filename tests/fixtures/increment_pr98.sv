module increment_pr98(
    input logic [4:0] a,
    input logic [64:0] counter,
    input logic [31:0] address,
    output logic [3:0] small_next,
    output logic [63:0] counter_next,
    output logic [31:0] address_next
);
    assign small_next = a[3:0] + 4'd1;
    assign counter_next = counter[63:0] + 1;
    assign address_next = {address[31:2], 2'b0} + 32'd4;
endmodule
