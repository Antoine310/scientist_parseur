module advanced_logic #(
    parameter int WIDTH = 8,
    parameter bit USE_XOR = 1'b1
) (
    input  logic [WIDTH-1:0] data_a,
    input  logic [WIDTH-1:0] data_b,
    input  logic [1:0] sel,
    input  logic [2:0] idx,
    output logic [WIDTH-1:0] result,
    output logic picked,
    output logic [WIDTH-1:0] mode_result
);
    logic [WIDTH-1:0] merged;
    assign merged = {data_a[WIDTH-1:4], data_b[3:0]};
    assign picked = data_a[idx];

    always_comb begin
        case (sel)
            2'b00: result = merged;
            2'b01: result = data_a;
            default: result = data_b;
        endcase
    end

    generate
        if (USE_XOR) begin : gen_logic
            assign mode_result = data_a ^ data_b;
        end else begin : gen_logic
            assign mode_result = data_a | data_b;
        end
    endgenerate
endmodule
