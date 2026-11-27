module state_conversions_pr118_tb;
    logic [1:0] src4;
    bit [1:0] src2;
    wire [1:0] dst2, dst4;
    state_conversions_pr118 dut(.*);
    function automatic logic state_value(input integer i);
        case(i)
            0: state_value=1'b0;
            1: state_value=1'b1;
            2: state_value=1'bx;
            3: state_value=1'bz;
            default: state_value=1'bx;
        endcase
    endfunction
    integer a,b,c,checks;
    reg [1:0] expected;
    initial begin
        checks=0;
        for(a=0;a<4;a=a+1)
            for(b=0;b<4;b=b+1)
                for(c=0;c<4;c=c+1) begin
                    src4={state_value(a),state_value(b)};
                    src2=c[1:0];
                    expected={(a==1),(b==1)};
                    #1;
                    if(dst2 !== expected) $fatal(1,"down mismatch: %b -> %b expected %b",src4,dst2,expected);
                    if(dst4 !== c[1:0]) $fatal(1,"up mismatch");
                    checks=checks+2;
                end
        if(checks!=128) $fatal(1,"wrong check count");
        $display("PR118_FOUR_STATE_PASS checks=%0d",checks);
        $finish;
    end
endmodule
