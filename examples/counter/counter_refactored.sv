// Une implementation volontairement differente mais fonctionnellement equivalente.
// La valeur suivante est calculee hors du always_ff.
module counter (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    output logic [7:0] count
);
    logic [7:0] incremented;
    assign incremented = count + 8'd1;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 8'd0;
        else if (enable)
            count <= incremented;
    end
endmodule
