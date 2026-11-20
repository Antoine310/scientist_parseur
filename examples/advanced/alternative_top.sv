module alternative_top (
    input  logic [7:0] data_a,
    input  logic [7:0] data_b,
    input  logic [1:0] sel,
    input  logic [2:0] idx,
    output logic [7:0] mode_result
);
    logic [7:0] unused_result;
    logic unused_picked;
    advanced_logic #(.WIDTH(8), .USE_XOR(1'b0)) dut (
        .data_a(data_a),
        .data_b(data_b),
        .sel(sel),
        .idx(idx),
        .result(unused_result),
        .picked(unused_picked),
        .mode_result(mode_result)
    );
endmodule
