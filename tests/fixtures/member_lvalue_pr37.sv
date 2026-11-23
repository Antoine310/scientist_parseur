// RTLPrep-owned standalone SystemVerilog fixture, tested with real slang.
// Explicitly no proof of the functional behavior of this RTL.
module member_lvalue_pr37 (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       en,
    input  logic [3:0] d,
    output logic [7:0] q,
    output logic [3:0] selected
);
  typedef struct packed {
    logic [3:0] high;
    logic [3:0] low;
  } bundle_t;

  bundle_t state;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      state <= '0;
    else if (en)
      state.low <= d;
  end

  assign q = state;
  assign selected = state.low;
endmodule
