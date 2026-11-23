// RTLPrep-owned SystemVerilog fixture. Real slang AST is the oracle for
// syntactic segment identification, not for behavior or equivalence.
module typed_segments_pr39 (
    input  logic [7:0] bus_i,
    output logic [15:0] packed_o,
    output logic [7:0] repeated_o,
    output logic [7:0] sliced_o,
    output logic [7:0] enum_alias_o
);
  typedef enum logic [2:0] { OP_A = 3'b101, OP_B = 3'b011 } opcode_t;
  localparam logic [2:0] EXPLICIT_OPCODE = 3'b101;

  always_comb begin
    packed_o = {5'b0, bus_i, EXPLICIT_OPCODE};
    repeated_o = {{4{bus_i[7]}}, bus_i[3:0]};
    // Slang's NamedValue type is an alias 'opcode_t', NOT an explicit
    // one-dimensional packed width. This MUST stay partial in bit_accesses.
    enum_alias_o = {5'b0, OP_A};
  end

  assign sliced_o = {bus_i[7:4], bus_i[3:0]};
endmodule
