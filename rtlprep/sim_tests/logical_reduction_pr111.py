import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def exhaustive_binary_logic(dut):
    for x in range(256):
        a,b,c,d=[(x>>i)&1 for i in range(4)]
        v=x>>4
        for name,value in zip(("a","b","c","d","v"),(a,b,c,d,v)):
            getattr(dut,name).value=value
        await Timer(1,unit="ns")
        expected=[a==1 and b==0,(a|b|c)==0,(a|b|c)==0 and d==1,
                  v!=0 and d==1,v!=0 or b==1,v==0]
        y=int(dut.y.value)
        for i,bit in enumerate(expected):
            assert (y>>i)&1==int(bit)
