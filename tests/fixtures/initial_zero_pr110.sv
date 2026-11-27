module initial_zero_pr110(
    input logic clk,
    input logic [7:0] data,
    output logic flag_q,
    output logic [5:2] word_q,
    output logic [7:0] byte_q,
    output logic [3:0] nonzero_q,
    output logic [3:0] param_q
);
    localparam logic [3:0] INIT_VALUE = 4'd3;
    initial flag_q = 1'b0;
    initial word_q = 0;
    initial byte_q = 8'd0;
    initial nonzero_q = 4'd5;
    initial param_q = INIT_VALUE;
    always @(posedge clk) begin
        flag_q <= data[0];
        word_q <= data[7:4];
        byte_q <= data;
    end
endmodule
