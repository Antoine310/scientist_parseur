module generate_nba_pr108(
    input logic clk, en,
    input logic [7:0] data,
    output logic flag_a, flag_b,
    output logic [3:0] word_a, word_b
);
    if (1) begin : gen_a
        logic flag_q;
        logic [3:0] word_q;
        always_ff @(posedge clk)
            if (en) begin
                flag_q <= data[2];
                word_q <= data[7:4];
            end
        assign flag_a = flag_q;
        assign word_a = word_q;
    end
    if (1) begin : gen_b
        logic flag_q;
        logic [3:0] word_q;
        always_ff @(posedge clk)
            if (en) begin
                flag_q <= data[3];
                word_q <= data[3:0];
            end
        assign flag_b = flag_q;
        assign word_b = word_q;
    end
endmodule
