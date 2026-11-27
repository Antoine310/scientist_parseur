import cocotb
from cocotb.triggers import Timer


def oracle(d,k,mode,n):
    value=d-2**n if mode and d>=2**(n-1) else d
    return (value//2**k)%2**n


@cocotb.test()
async def exhaustive_controlled_sign(dut):
    for d in range(256):
        dut.d.value=d
        for k in range(8):
            dut.k.value=k
            for mode in range(2):
                dut.mode.value=mode
                await Timer(1,unit="ns")
                assert int(dut.y8.value)==oracle(d,k,mode,8)
                assert int(dut.y4.value)==oracle(d//16,k%4,mode,4)
