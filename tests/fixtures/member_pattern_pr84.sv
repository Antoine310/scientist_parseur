package member_pattern_pr84_pkg;
    typedef enum logic [1:0] {LO = 2'b01, HI = 2'b10} Mode_t;
    typedef struct packed {
        logic a;
        logic b;
        Mode_t mode;
        logic c;
    } Word_t;
endpackage
module member_pattern_pr84(input logic clk, input logic [4:0] data,
                           input logic choose, output logic [7:0] readback);
    import member_pattern_pr84_pkg::*;
    Word_t d, q;
    assign d = data;
    always_ff @(posedge clk)
        q <= '{a: d.a, b: d.b, mode: HI, c: 1'b0};
    assign readback = {choose ? 1'b1 : 1'b0, 2'b0, q.a, q.b, q.mode, q.c};
endmodule
