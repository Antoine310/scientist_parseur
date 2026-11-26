module aggregate_pr78(
    input logic [7:0] data,
    output logic [2:0] concat_hi, struct_hi, union_hi,
    output logic [4:0] concat_lo, struct_lo
);
    typedef struct packed {
        logic [2:0] high;
        logic [4:0] low;
    } pair_t;
    typedef union packed {
        logic [7:0] word;
        pair_t parts;
    } overlay_t;
    pair_t bundle;
    overlay_t overlay;
    assign {concat_hi, concat_lo} = data;
    assign bundle = data;
    assign struct_hi = bundle.high;
    assign struct_lo = bundle.low;
    assign overlay.word = data;
    assign union_hi = overlay.parts.high;
endmodule
