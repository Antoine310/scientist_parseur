module function_pr58(input logic [7:0] a,b,
    output logic [7:0] mix_o, both_o, global_o, branch_o, cancel_o);
  function automatic logic [7:0] mix(input logic [7:0] x,y);
    return x ^ 8'h5a;
  endfunction
  function automatic logic [7:0] both(input logic [7:0] x,y);
    return x ^ y;
  endfunction
  function automatic logic [7:0] external_read(input logic [7:0] x);
    return x ^ b;
  endfunction
  function automatic logic [7:0] branch(input logic [7:0] x,y);
    if (x[0]) return x;
    return y;
  endfunction
  function automatic logic [7:0] cancel(input logic [7:0] x);
    return x ^ x;
  endfunction
  assign mix_o = mix(a,b);
  assign both_o = both(a,b);
  assign global_o = external_read(a);
  assign branch_o = branch(a,b);
  assign cancel_o = cancel(a);
endmodule
