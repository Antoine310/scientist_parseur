// RTLPrep-owned probe harness. No upstream CVA6 RTL is copied here.
// The selected configuration is the upstream cv32a6_imac_sv32 cva6_cfg;
// it is elaborated through upstream build_config_pkg::build_config.
module rtlprep_cva6_compressed_decoder (
    input  logic [31:0] instr_i,
    output logic [31:0] instr_o,
    output logic        illegal_instr_o,
    output logic        is_macro_instr_o,
    output logic        is_compressed_o,
    output logic        is_zcmt_instr_o
);
  localparam config_pkg::cva6_cfg_t SelectedCfg =
      build_config_pkg::build_config(cva6_config_pkg::cva6_cfg);

  compressed_decoder #(.CVA6Cfg(SelectedCfg)) decoder_i (
      .instr_i(instr_i),
      .instr_o(instr_o),
      .illegal_instr_o(illegal_instr_o),
      .is_macro_instr_o(is_macro_instr_o),
      .is_compressed_o(is_compressed_o),
      .is_zcmt_instr_o(is_zcmt_instr_o)
  );
endmodule
