module vector_concat_nba_pr109(
    input logic clk,
    input logic [7:0] data,
    output logic [5:2] word_q,
    output logic flag_q,
    output logic [3:0] split_q
);
    always_ff @(posedge clk) begin
        {word_q, flag_q} <= {data[7:5], data[1:0]};
        {split_q[3:2], split_q[1:0]} <= {data[4], data[7:5]};
    end
endmodule
