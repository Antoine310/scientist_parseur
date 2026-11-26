package member_cond_pr85_pkg;
    typedef enum logic [1:0] {OFF=2'b00, DIRTY=2'b11} Mode_t;
    typedef struct packed {logic a; logic b;} Pair_t;
endpackage
module member_cond_pr85 #(
    parameter logic signed [31:0] FPU=0,
    parameter logic signed [31:0] ZFINX=0,
    parameter logic signed [31:0] ENABLED=1
)(input logic [1:0] data, input logic choose,
  output logic [3:0] disabled_o, output logic [3:0] enabled_o);
    import member_cond_pr85_pkg::*;
    Pair_t bundle;
    Mode_t mode;
    assign bundle=data;
    assign mode=choose ? DIRTY : OFF;
    assign disabled_o={(FPU==1 && ZFINX==0) ? mode : OFF,bundle.a,bundle.b};
    assign enabled_o={(ENABLED==1 && ZFINX==0) ? mode : OFF,bundle.a,bundle.b};
endmodule
