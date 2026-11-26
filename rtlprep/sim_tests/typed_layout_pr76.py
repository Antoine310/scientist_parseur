import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def package_types(dut):
    for v in range(256):
        p=(v*257)^0x5A3C
        d=v&15
        state=(1,2,4)[v%3]
        for i in range(4):
            dut.p.value=p
            dut.d.value=d
            dut.state_i.value=state
            dut.addr_i.value=i
            await Timer(2,unit="ns")
            assert int(dut.flag_o.value)==((state>>1)&1)
            assert int(dut.read_o.value)==((p>>(4*i))&15)
            assert int(dut.write_o.value)==d<<(4*i)
