module dependency_top(
    input logic clk,
    input logic rst_n,
    input logic enable,
    input logic a,
    input logic b,
    input logic sel,
    output logic out,
    output logic [3:0] count
);
    logic interm;
    logic_leaf child(.a(a), .b(b), .sel(sel), .y(interm));
    assign out = interm;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 4'd0;
        else if (enable)
            count <= count + 4'd1;
    end
endmodule
