package enum_members_pr81_pkg;
    typedef enum logic [1:0] {LO = 2'b01, HI = 2'b10} Mode_t;
    typedef struct packed {
        logic marker;
        Mode_t mode;
        logic tail;
    } Word_t;
endpackage
module enum_members_pr81(input logic choose, input logic marker,
                          output logic [3:0] packed_o);
    import enum_members_pr81_pkg::*;
    Word_t bundle;
    always_comb begin
        bundle.marker = marker;
        bundle.tail = ~marker;
        if (choose) bundle.mode = HI;
        else bundle.mode = LO;
    end
    assign packed_o = bundle;
endmodule
