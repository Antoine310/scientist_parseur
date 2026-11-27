module constant_conversions_pr115(
    input logic [15:0] d,
    output logic [3:0][63:0] counter_q,
    output logic [3:0][31:0] event_q,
    output logic [3:0][4:0] index_lut
);
    localparam integer HI_START = 16;
    for (genvar j=0; j<4; j++) begin : g
        assign counter_q[j] = 32'd0;
        assign index_lut[j] = $unsigned(j);
        if (j!=3) begin : z
            assign event_q[j] = 32'd0;
        end else begin : p
            assign event_q[j][31:HI_START] = 32'd0;
            assign event_q[3][15:0] = d;
        end
    end
endmodule
