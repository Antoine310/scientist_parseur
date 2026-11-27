import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def binary_shift_oracle(dut):
    for d in range(256):
        dut.d.value=d
        for k in range(32):
            dut.k.value=k
            await Timer(1,unit="ns")
            assert int(dut.fixed_o.value)==(d*4)%256
            assert int(dut.left_o.value)==(d*2**(k%8))%256
            assert int(dut.right_o.value)==(d//2**(k%8))%16
            assert int(dut.mask_o.value)==(0xfffffffe*2**k)%2**32
