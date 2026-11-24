// Formal-only instrumentation: expose the two packed state entries.
module ras_formal_probe (
  input logic clk_i, rst_ni, flush_bp_i, push_i, pop_i,
  input logic [31:0] data_i,
  output logic [65:0] state_o,
  output logic [32:0] top_o
);
  localparam config_pkg::cva6_cfg_t SelectedCfg =
      build_config_pkg::build_config(cva6_config_pkg::cva6_cfg);
  typedef struct packed { logic valid; logic [31:0] ra; } ras_t;
  ras_t data_o;
  ras #(.CVA6Cfg(SelectedCfg), .ras_t(ras_t), .DEPTH(2)) ras_i (
    .clk_i(clk_i), .rst_ni(rst_ni), .flush_bp_i(flush_bp_i),
    .push_i(push_i), .pop_i(pop_i), .data_i(data_i), .data_o(data_o)
  );
  assign state_o = ras_i.stack_q;
  assign top_o = data_o;
endmodule
