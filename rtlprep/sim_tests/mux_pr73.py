import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def exhaustive_mux(dut):
    for a in range(16):
        for b in range(16):
            for s in range(2):
                for t in range(2):
                    dut.a.value=a
                    dut.b.value=b
                    dut.p.value=(a<<4)|b
                    dut.s.value=s
                    dut.t.value=t
                    await Timer(2,unit="ns")
                    assert int(dut.y.value)==(a if s else b)
                    assert int(dut.y_nested.value)==((a if t else b) if s else 0)
                    assert int(dut.y_cmp.value)==(a if (a&1)==(b&1) else b)
                    assert int(dut.y_packed.value)==(a if s else b)
                    assert int(dut.y_const.value)==(a if t else 0)
