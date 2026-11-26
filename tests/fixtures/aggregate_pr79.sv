package aggregate_pr79_pkg;
    typedef struct packed {
        logic [7:5] high;
        logic [4:0] low;
    } Pair_t;
endpackage
module aggregate_pr79(
    input logic [2:0] high_i,
    input logic [4:0] low_i,
    output logic [7:5] high_o,
    output logic [4:0] low_o,
    output logic [7:0] packed_o
);
    aggregate_pr79_pkg::Pair_t bundle;
    assign bundle.high = high_i;
    assign bundle.low = low_i;
    assign high_o = bundle.high;
    assign low_o = bundle.low;
    assign packed_o = bundle;
endmodule
