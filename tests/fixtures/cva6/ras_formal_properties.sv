// Independent two-entry transition model, not copied from the DUT.
module ras_formal_properties(input wire clk_i, rst_ni, flush_bp_i, push_i, pop_i,
                             input wire [31:0] data_i);
  wire [65:0] state_o;
  wire [32:0] top_o;
  ras_formal_probe dut(.clk_i(clk_i), .rst_ni(rst_ni), .flush_bp_i(flush_bp_i),
    .push_i(push_i), .pop_i(pop_i), .data_i(data_i), .state_o(state_o), .top_o(top_o));
  reg [32:0] upper, lower;
  reg initialized = 1'b0;
  initial assume(!rst_ni);
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      upper <= 0;
      lower <= 0;
      initialized <= 1;
    end else if (flush_bp_i) begin
      upper <= 0;
      lower <= 0;
    end else case ({push_i,pop_i})
      2'b10: begin upper <= {1'b1,data_i}; lower <= upper; end
      2'b01: begin upper <= lower; lower <= 0; end
      2'b11: upper <= {1'b1,data_i};
      default: begin end
    endcase
  end
  always @(*) if (initialized) begin
    assert(state_o == {lower,upper});
    assert(top_o == upper);
  end
  // Separate cover witnesses ensure active nontrivial state and control cases.
  always @(posedge clk_i) if (initialized && rst_ni) begin
    cover(upper[32] && lower[32] && upper != lower && !flush_bp_i && push_i && pop_i);
    cover(upper[32] && flush_bp_i && push_i);
    cover(upper[32] && !flush_bp_i && !push_i && !pop_i);
  end
endmodule
