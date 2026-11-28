module arithmetic_range_pr125(
    input logic [31:0] csr_wdata_int,
    input logic [1:0] sel,
    output logic [4:0] fflags_n,
    output logic [2:0] frm_n
);
    localparam logic signed [31:0] C_FFLAG=5;
    localparam logic signed [31:0] C_RM=3;
    always_comb begin
        fflags_n='0;
        frm_n='0;
        case (sel)
            2'd0: fflags_n=csr_wdata_int[C_FFLAG-1:0];
            2'd1: frm_n=csr_wdata_int[C_RM-1:0];
            2'd2: begin
                fflags_n=csr_wdata_int[C_FFLAG-1:0];
                frm_n=csr_wdata_int[C_RM+C_FFLAG-1:C_FFLAG];
            end
            default: begin end
        endcase
    end
endmodule
