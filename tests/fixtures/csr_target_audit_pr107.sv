package csr_target_audit_pr107_pkg;
    typedef struct packed {
        logic flag_a;
        logic flag_b;
    } Pair_t;
endpackage
module csr_target_audit_pr107(
    input logic clk,
    input logic [3:0] data,
    output logic [1:0] packed_o,
    output logic flag_o,
    output logic [3:0] word_o
);
    csr_target_audit_pr107_pkg::Pair_t bundle;
    always_comb begin
        bundle.flag_a = data[3];
        bundle.flag_b = data[1];
    end
    assign packed_o = bundle;
    if (1) begin : gen_regs
        logic flag_q;
        logic [3:0] word_q;
        always_ff @(posedge clk) begin
            flag_q <= data[2];
            word_q <= data[3:0];
        end
        assign flag_o = flag_q;
        assign word_o = word_q;
    end
endmodule
