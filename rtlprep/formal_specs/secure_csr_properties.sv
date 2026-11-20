// Independent security contract for an educational protected CSR.
// Assume reset is active at the initial formal instant. Thereafter,
// inputs can vary freely; never assume privileged or debug-locked values.
module secure_csr_formal (
    input wire       clk,
    input wire       rst_n,
    input wire       write_i,
    input wire       machine_mode_i,
    input wire       debug_locked_i,
    input wire [7:0] wdata_i
);
    wire [7:0] value_o;
    wire write_accepted_o;
    secure_csr dut(
        .clk(clk), .rst_n(rst_n),
        .write_i(write_i), .machine_mode_i(machine_mode_i),
        .debug_locked_i(debug_locked_i), .wdata_i(wdata_i),
        .value_o(value_o), .write_accepted_o(write_accepted_o)
    );

    wire spec_accepted = write_i && machine_mode_i && !debug_locked_i;
    reg [7:0] spec_value = 8'h00;
    reg initialized = 1'b0;

    initial assume(!rst_n);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spec_value <= 8'h00;
            initialized <= 1'b1;
        end else if (spec_accepted) begin
            spec_value <= wdata_i;
        end
    end

    // Invariants hold for all symbolic steps, not only sampled clock edges.
    // No "assume" is used to exclude unauthorized writes.
    always @(*) begin
        if (initialized) begin
            assert(write_accepted_o == spec_accepted);
            assert(value_o == spec_value);
            if (write_i && !machine_mode_i)
                assert(!write_accepted_o);
            if (debug_locked_i)
                assert(!write_accepted_o);
        end
    end

    // A reachable legitimate write witness prevents a vacuous all-denied
    // result, but cover PASS is not comprehensive functional coverage.
    always @(posedge clk) begin
        if (initialized && rst_n)
            cover(value_o == 8'hA5);
    end
endmodule
