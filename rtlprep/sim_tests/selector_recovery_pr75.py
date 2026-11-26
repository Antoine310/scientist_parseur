import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def generated_selectors(dut):
    for value in range(256):
        a=value&3
        b=(value>>2)&3
        p=value
        q=value^0xA5
        for s in range(4):
            dut.a.value=a
            dut.b.value=b
            dut.p.value=p
            dut.q.value=q
            dut.s.value=s
            await Timer(2,unit="ns")
            assert int(dut.y.value)==a|b
            assert int(dut.words.value)==sum((((p if s&(1<<g) else q)>>(4*g))&15)<<(4*g) for g in range(2))
            assert int(dut.fixed_out.value)==1
