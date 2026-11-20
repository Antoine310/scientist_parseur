// Propriétés de la FSM handshake : automate de référence séparé du DUT.
module handshake_fsm_formal (
    input wire clk,
    input wire rst_n,
    input wire start,
    input wire ack
);
    wire busy, done;
    handshake_fsm dut(
        .clk(clk), .rst_n(rst_n), .start(start), .ack(ack),
        .busy(busy), .done(done)
    );

    localparam [1:0] IDLE = 2'd0, BUSY = 2'd1, DONE = 2'd2;
    reg [1:0] expected_state = IDLE;
    reg initialized = 1'b0;

    initial assume(!rst_n);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            expected_state <= IDLE;
            initialized <= 1'b1;
        end else begin
            case (expected_state)
                IDLE: if (start) expected_state <= BUSY;
                BUSY: if (ack)   expected_state <= DONE;
                DONE:           expected_state <= IDLE;
                default:        expected_state <= IDLE;
            endcase
        end
    end

    always @(*) begin
        if (initialized) begin
            assert(busy == (expected_state == BUSY));
            assert(done == (expected_state == DONE));
            assert(!(busy && done));
        end
    end

    always @(posedge clk) begin
        // Vérifie que DONE est atteignable, plutôt que seulement prouver
        // des propriétés sous des hypothèses qui bloquent toute activité.
        if (initialized && rst_n)
            cover(done);
    end
endmodule
