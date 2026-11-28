module parameter_mux_leaf_pr122 #(
    parameter logic signed [31:0] CFG=0
)(
    input logic [1:0][31:0] data_i,
    output logic [31:0] y0,y1
);
    assign y0 = !CFG ? 32'd0 : data_i[0];
    assign y1 = !CFG ? 32'd0 : data_i[1];
endmodule

module parameter_mux_pr122 #(
    parameter logic signed [31:0] CFG0=0,
    parameter logic signed [31:0] CFG1=1
)(
    input logic [1:0][31:0] data_i,
    output logic [31:0] zero0,zero1,one0,one1
);
    parameter_mux_leaf_pr122 #(.CFG(CFG0)) u_zero(.data_i(data_i),.y0(zero0),.y1(zero1));
    parameter_mux_leaf_pr122 #(.CFG(CFG1)) u_one(.data_i(data_i),.y0(one0),.y1(one1));
endmodule
