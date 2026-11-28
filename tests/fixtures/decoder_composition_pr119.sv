module decoder_composition_pr119(
    input logic [5:0] waddr_a, waddr_b,
    input logic we_a_i, we_b_i,
    output logic [31:0] we_a_dec, we_b_dec
);
    for (genvar gidx=0; gidx<32; gidx++) begin : gen_dec
        assign we_a_dec[gidx] = (waddr_a == gidx) ? we_a_i : 1'b0;
        assign we_b_dec[gidx] = (waddr_b == gidx) ? we_b_i : 1'b0;
    end
endmodule
