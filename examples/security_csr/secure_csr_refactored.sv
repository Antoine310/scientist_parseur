// Same authorization contract as the gold module, different RTL structure.
module secure_csr (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       write_i,
    input  logic       machine_mode_i,
    input  logic       debug_locked_i,
    input  logic [7:0] wdata_i,
    output logic [7:0] value_o,
    output logic       write_accepted_o
);
    logic authorized;
    assign authorized = machine_mode_i && !debug_locked_i;
    assign write_accepted_o = authorized && write_i;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            value_o <= 8'h00;
        else if (write_accepted_o)
            value_o <= wdata_i;
    end
endmodule
