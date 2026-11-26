module local_members_pr82(
    input logic [11:0] data,
    output logic [1:0][3:0] hi,
    output logic [0:1][1:0] lo,
    output logic [11:0] zero_o
);
    typedef struct packed {
        logic [1:0][3:0] upper;
        logic [0:1][1:0] lower;
    } Pair_t;
    Pair_t bundle, zero_bundle;
    assign bundle = data;
    assign hi = bundle.upper;
    assign lo = bundle.lower;
    assign zero_bundle.upper = '0;
    assign zero_bundle.lower = '0;
    assign zero_o = zero_bundle;
endmodule
