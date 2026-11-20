// Variante FSM : meme interface/semantique, expression differente du next-state.
// Le diagnostic FORMAL garde la meme logique que dans la version originale.
module handshake_fsm (
    input  logic clk,
    input  logic rst_n,
    input  logic start,
    input  logic ack,
    output logic busy,
    output logic done
`ifdef FORMAL
    , output wire [1:0] formal_state
`endif
);
    typedef enum logic [1:0] {IDLE, BUSY, DONE} state_t;
    state_t state_q, state_d;

    always_comb begin
        state_d = state_q;
        if (state_q == IDLE) begin
            if (start)
                state_d = BUSY;
        end else if (state_q == BUSY) begin
            if (ack)
                state_d = DONE;
        end else begin
            state_d = IDLE;
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_q <= IDLE;
        else
            state_q <= state_d;
    end
    assign busy = state_q == BUSY;
    assign done = state_q == DONE;
`ifdef FORMAL
    assign formal_state = state_q;
`endif
endmodule
