// RTLPrep-owned harness; actual RAS implementation is from pinned CVA6.
module rtlprep_cva6_ras (
    input logic clk_i, rst_ni, flush_bp_i, push_i, pop_i,
    input logic [31:0] data_i,
    output logic valid_o,
    output logic [31:0] ra_o
);
  localparam config_pkg::cva6_cfg_t SelectedCfg =
      build_config_pkg::build_config(cva6_config_pkg::cva6_cfg);
  typedef struct packed {
    logic valid;
    logic [SelectedCfg.VLEN-1:0] ra;
  } ras_t;
  ras_t data_o;
  ras #(.CVA6Cfg(SelectedCfg), .ras_t(ras_t), .DEPTH(2)) ras_i (
    .clk_i(clk_i), .rst_ni(rst_ni), .flush_bp_i(flush_bp_i),
    .push_i(push_i), .pop_i(pop_i), .data_i(data_i), .data_o(data_o)
  );
  assign valid_o = data_o.valid;
  assign ra_o = data_o.ra;
endmodule
