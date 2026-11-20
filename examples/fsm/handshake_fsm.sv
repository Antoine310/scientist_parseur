// FSM d'entraînement : start lance une opération, ack la termine.
// busy reste à 1 jusqu'à ack ; done pulse pendant un cycle.
module handshake_fsm (
    input  logic clk,
    input  logic rst_n,
    input  logic start,
    input  logic ack,
    output logic busy,
    output logic done
`ifdef FORMAL
    // Port de diagnostic présent UNIQUEMENT avec Yosys read -formal.
    // Aucun effet sur la simulation/synthèse normale du DUT.
    , output wire [1:0] formal_state
`endif
);
    typedef enum logic [1:0] {IDLE, BUSY, DONE} state_t;
    state_t state_q, state_d;

    always_comb begin
        state_d = state_q;
        case (state_q)
            IDLE: if (start) state_d = BUSY;
            BUSY: if (ack)   state_d = DONE;
            DONE:           state_d = IDLE;
            default:        state_d = IDLE;
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_q <= IDLE;
        else
            state_q <= state_d;
    end

    assign busy = (state_q == BUSY);
    assign done = (state_q == DONE);
`ifdef FORMAL
    assign formal_state = state_q;
`endif
endmodule
