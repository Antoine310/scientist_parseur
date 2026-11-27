module capture_audit_pr102(
    input logic [8:0] a,b,
    input logic [1:0] mode,
    input logic plain,
    output logic hidden,
    output logic [0:0] visible,
    output logic passthrough
);
    assign hidden = $signed({a[7] & mode[0], a[7:0]}) >
                    $signed({b[7] & mode[0], b[7:0]});
    assign visible[0] = $signed({a[7] & mode[0], a[7:0]}) >
                        $signed({b[7] & mode[0], b[7:0]});
    assign passthrough = plain;
endmodule
