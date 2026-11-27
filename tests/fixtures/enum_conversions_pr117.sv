package enum_conversions_pkg;
    typedef enum logic [3:0] {OP_A, OP_B} op_t;
    typedef enum logic [2:0] {FMT_A = 32'd2, FMT_B = 32'd5} fmt_t;
    typedef enum logic [1:0] {S0, S1, S2, S3} state_t;
endpackage
module enum_conversions_pr117(
    input logic sel,
    input logic [7:0] word,
    output logic [3:0] op,
    output logic [2:0] fmt,
    output enum_conversions_pkg::state_t state
);
    always_comb begin
        if (sel) begin
            op = enum_conversions_pkg::OP_B;
            fmt = enum_conversions_pkg::FMT_B;
        end else begin
            op = enum_conversions_pkg::OP_A;
            fmt = enum_conversions_pkg::FMT_A;
        end
        state = enum_conversions_pkg::state_t'(word[4:3]);
    end
endmodule
