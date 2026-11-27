import cocotb
from cocotb.triggers import Timer


def oracle(a,b,n):
    def signed(x):
        return x if x<2**(n-1) else x-2**n
    return (signed(a)*signed(b))%(2**(2*n))


def boundary(n):
    h=2**(n-1)
    return [0,1,2,3,7,h-2,h-1,h,h+1,2*h-2,2*h-1,h//2]


@cocotb.test()
async def signed_products(dut):
    dut.a9.value=dut.b9.value=dut.a17.value=dut.b17.value=0
    for a in range(16):
        for b in range(16):
            dut.a4.value=a|(b<<4)
            dut.b4.value=b|((a^8)<<4)
            await Timer(1,unit="ns")
            p=int(dut.p4.value)
            assert p&255==oracle(a,b,4)
            assert p>>8==oracle(b,a^8,4)
    v9,v17=boundary(9),boundary(17)
    for i in range(12):
        for j in range(12):
            dut.a9.value=v9[i]
            dut.b9.value=v9[j]
            dut.a17.value=v17[i]
            dut.b17.value=v17[j]
            await Timer(1,unit="ns")
            assert int(dut.p9.value)==oracle(v9[i],v9[j],9)
            assert int(dut.p17.value)==oracle(v17[i],v17[j],17)
