import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def increment_boundaries(dut):
    for a in range(16):
        dut.a.value=a
        await Timer(1,unit="ns")
        assert int(dut.small_next.value)==(a+1)%16
    for v in (0,1,2,3,0xffffffff,0x7fffffffffffffff,0x8000000000000000,0xffffffffffffffff):
        dut.counter.value=v
        await Timer(1,unit="ns")
        assert int(dut.counter_next.value)==(v+1)%(1<<64)
    for v in (0,1,2,3,0x7fffffff,0xfffffffc,0xfffffffe,0xffffffff):
        dut.address.value=v
        await Timer(1,unit="ns")
        assert int(dut.address_next.value)==((v//4+1)*4)%(1<<32)
