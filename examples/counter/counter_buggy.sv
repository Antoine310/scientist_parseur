// Circuit INTENTIONNELLEMENT FAUX pour vérifier les échecs de simulation.
// La spécification exige +1, ce mutant effectue +2.
module counter (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    output logic [7:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 8'd0;
        else if (enable)
            count <= count + 8'd2; // BUG volontaire
    end
endmodule
