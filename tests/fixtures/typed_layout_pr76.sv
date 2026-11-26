package typed_layout_pkg;
  typedef enum logic [2:0] {S0=3'b001,S1=3'b010,S2=3'b100} state_t;
  typedef enum logic [1:0] {A0,A1,A2,A3} addr_t;
  localparam integer FLAG_INDEX=1;
endpackage

module typed_layout_pr76(
  input typed_layout_pkg::state_t state_i,
  input typed_layout_pkg::addr_t addr_i,
  input logic [3:0][3:0] p,
  input logic [3:0] d,
  output logic flag_o,
  output logic [3:0] read_o,
  output logic [3:0][3:0] write_o
);
  assign flag_o = state_i[typed_layout_pkg::FLAG_INDEX];
  assign read_o = p[addr_i[1:0]];
  always_comb begin
    write_o='0;
    write_o[addr_i[1:0]]=d;
  end
endmodule
