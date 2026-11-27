module comparison_pr100(
    input logic [8:0] a,b,
    input logic [2:0] instr,
    input logic [1:0] count,
    output logic equal_byte, compressed, full
);
    localparam int unsigned FIFO_DEPTH=2;
    localparam int unsigned ADDR_DEPTH=1;
    assign equal_byte = a[7:0] == b[7:0];
    assign compressed = instr[1:0] != 2'b11;
    assign full = count == FIFO_DEPTH[ADDR_DEPTH:0];
endmodule
