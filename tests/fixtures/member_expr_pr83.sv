package member_expr_pr83_pkg;
    typedef struct packed {
        logic a;
        logic b;
        logic c;
    } Triple_t;
endpackage
module member_expr_pr83(input logic [2:0] data, input logic [1:0] extra,
                        output logic flag, output logic [4:0] readback);
    member_expr_pr83_pkg::Triple_t bundle;
    assign bundle = data;
    assign flag = bundle.a && !(bundle.b && !bundle.c);
    assign readback = {bundle.a, extra, bundle.b, bundle.c};
endmodule
