import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def priority(dut):
    dut.clk.value = 0
    dut.rst_n.value = 1
    dut.en_a.value = 0
    dut.en_b.value = 0
    dut.a.value = 0
    dut.b.value = 0
    await Timer(2,unit="ns")
    dut.rst_n.value = 0
    await Timer(2,unit="ns")
    assert int(dut.q.value) == 0
    dut.rst_n.value = 1
    q = 0
    for i in range(64):
        ea,eb = (i>>1)&1,i&1
        a,b = (i*3+1)&255,(i*5+129)&255
        dut.en_a.value = ea
        dut.en_b.value = eb
        dut.a.value = a
        dut.b.value = b
        await Timer(2,unit="ns")
        assert int(dut.q.value) == q
        dut.clk.value = 1
        await Timer(2,unit="ns")
        q = b if eb else a if ea else q
        assert int(dut.q.value) == q, f"PR47_NBA_MISMATCH cycle={i} a={ea} b={eb}"
        dut.clk.value = 0
        await Timer(2,unit="ns")
