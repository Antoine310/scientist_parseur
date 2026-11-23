module imported_top (
  input logic clk,
  input logic rst_n,
  output logic [7:0] count
);
  import import_pkg::*;
  `include "config.svh"
  logic [WIDTH-1:0] internal_count;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      internal_count <= '0;
    else
      internal_count <= internal_count + `INCREMENT;
  end
  assign count = internal_count;
endmodule
