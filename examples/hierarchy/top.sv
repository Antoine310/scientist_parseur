module hierarchy_top (
    input logic clk,
    input logic enable,
    output logic [1:0] status
);
    leaf first  (.enable(enable), .status(status[0]));
    leaf second (.enable(enable), .status(status[1]));
endmodule
