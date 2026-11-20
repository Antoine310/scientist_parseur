// Propriétés du compteur. Référence indépendante de l'implémentation RTL.
// Le modèle utilise un reset réellement exercé avant les assertions.
module counter_formal (
    input wire clk,
    input wire rst_n,
    input wire enable
);
    wire [7:0] count;
    counter dut(.clk(clk), .rst_n(rst_n), .enable(enable), .count(count));

    reg [7:0] reference_count = 8'd0;
    reg initialized = 1'b0;

    // Un reset initial est la seule hypothèse d'environnement : après ce
    // point, rst_n et enable restent libres pour la recherche formelle.
    initial assume(!rst_n);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reference_count <= 8'd0;
            initialized <= 1'b1;
        end else if (enable) begin
            reference_count <= reference_count + 8'd1;
        end
    end

    // L'invariant doit être évalué à CHAQUE pas formel, pas uniquement
    // lorsqu'un front d'horloge est librement choisi par le solveur.
    // Sinon, l'induction pourrait construire des états impossibles pendant
    // plusieurs cycles sans front et conclure UNKNOWN.
    always @(*) begin
        if (initialized)
            assert(count == reference_count);
    end

    always @(posedge clk) begin
        // Non-vacuité : au moins trois incréments doivent être atteignables.
        if (initialized && rst_n)
            cover(count == 8'd3);
    end
endmodule
