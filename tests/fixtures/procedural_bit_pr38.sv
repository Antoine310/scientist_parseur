// RTLPrep-owned RTL for true slang v12.1 procedural bit access tests.
// No third-party RTL copied and no equivalence / functional claim.
module procedural_bit_pr38 (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       en,
    input  logic [1:0] mode,
    input  logic [7:0] din,
    output logic [7:0] reg_q,
    output logic [3:0] comb_q
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      reg_q <= '0;
    else if (en)
      reg_q[3:0] <= din[7:4];
  end

  always_comb begin
    comb_q = reg_q[3:0];
    case (mode)
      2'd1:   comb_q[1:0] = din[3:2];
      default: comb_q[1:0] = din[1:0];
    endcase
  end
endmodule
