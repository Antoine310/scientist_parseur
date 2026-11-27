module walker_exclusions_pr105(
    input logic clk,
    input logic [1:0] a,
    output logic x,y,q,
    output wire [0:0] visible,
    output wire plain
);
    initial begin
        x = 1'b0;
        y = a[0];
    end
    always @(posedge clk)
        repeat (2) q <= a[1];
    assign visible[0] = a[0];
    assign plain = clk;
endmodule
