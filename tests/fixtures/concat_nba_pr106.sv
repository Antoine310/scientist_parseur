module concat_nba_pr106(
    input logic clk, rst, serial_in,
    output logic ck, qq, q
);
    always @(posedge clk)
        if (rst)
            {ck, qq, q} <= 3'h0;
        else
            {ck, qq, q} <= {qq, q, serial_in};
endmodule
