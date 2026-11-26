package member_occ_pr87_pkg;
    typedef struct packed { logic a; logic b; } Pair_t;
endpackage
module member_occ_pr87(input logic [1:0] data, output logic a, output logic b);
    member_occ_pr87_pkg::Pair_t bundle;
    assign bundle=data;
    assign a=bundle.a; assign b=bundle.b;
endmodule
