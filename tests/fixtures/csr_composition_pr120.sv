package csr_composition_pkg;
    typedef enum logic [11:0] {CSR_MCYCLE=12'hb00, CSR_MCYCLEH=12'hb80} csr_num_e;
    localparam logic signed [31:0] MHPMCOUNTER_WIDTH=64;
endpackage
module csr_composition_pr120(
    input csr_composition_pkg::csr_num_e csr_addr_i,
    input logic csr_we_int,
    input logic [31:0] inhibit,
    output logic [31:0] mhpmcounter_write_lower, mhpmcounter_write_upper
);
    import csr_composition_pkg::*;
    for (genvar wcnt_gidx=0; wcnt_gidx<32; wcnt_gidx++) begin : gen_dec
        assign mhpmcounter_write_lower[wcnt_gidx] = csr_we_int && (csr_addr_i == CSR_MCYCLE + wcnt_gidx);
        assign mhpmcounter_write_upper[wcnt_gidx] = !inhibit[wcnt_gidx] && csr_we_int &&
            (csr_addr_i == CSR_MCYCLEH + wcnt_gidx) && (MHPMCOUNTER_WIDTH == 64);
    end
endmodule
