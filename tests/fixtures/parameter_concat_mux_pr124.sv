module parameter_concat_mux_leaf_pr124 #(
    parameter logic signed [31:0] FPU=0
)(
    input logic [4:0] fflags_q,
    input logic [2:0] frm_q,
    output logic [31:0] flags_o,frm_o,fcsr_o
);
    assign flags_o = (FPU == 1) ? {27'd0, fflags_q} : '0;
    assign frm_o = (FPU == 1) ? {29'd0, frm_q} : '0;
    assign fcsr_o = (FPU == 1) ? {24'd0, frm_q, fflags_q} : '0;
endmodule

module parameter_concat_mux_pr124 #(
    parameter logic signed [31:0] CFG0=0,
    parameter logic signed [31:0] CFG1=1
)(
    input logic [4:0] fflags_q,
    input logic [2:0] frm_q,
    output logic [31:0] flags0,frm0,fcsr0,flags1,frm1,fcsr1
);
    parameter_concat_mux_leaf_pr124 #(.FPU(CFG0)) u_zero(
        .fflags_q(fflags_q),.frm_q(frm_q),.flags_o(flags0),.frm_o(frm0),.fcsr_o(fcsr0));
    parameter_concat_mux_leaf_pr124 #(.FPU(CFG1)) u_one(
        .fflags_q(fflags_q),.frm_q(frm_q),.flags_o(flags1),.frm_o(frm1),.fcsr_o(fcsr1));
endmodule
