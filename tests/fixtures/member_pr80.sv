package member_pr80_pkg;
    typedef struct packed {
        logic a;
        logic b;
        logic c;
        logic d;
    } Four_t;
endpackage
module member_pr80(input logic [3:0] data, output logic [3:0] packed_o);
    member_pr80_pkg::Four_t bundle;
    assign bundle.a = data[3];
    assign bundle.b = 1'b0;
    assign bundle.c = data[1];
    assign bundle.d = 1'b1;
    assign packed_o = bundle;
endmodule
