module dynamic_pr74(
  input logic [3:0][3:0] p,
  input logic [3:0] d,
  input logic [1:0] idx,
  output logic read_bit,
  output logic [3:0] read_word, read_unpacked,
  output logic [3:0][3:0] write_word, write_constant
);
  logic [3:0] u[0:3];
  assign u[0] = p[0];
  assign u[1] = p[1];
  assign u[2] = p[2];
  assign u[3] = p[3];
  assign read_bit = p[0][idx];
  assign read_word = p[idx];
  assign read_unpacked = u[idx];
  always_comb begin
    write_word = '0;
    write_word[idx] = d;
    write_constant = '0;
    write_constant[idx] = '1;
  end
endmodule
