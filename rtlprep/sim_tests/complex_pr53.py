import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def constructs(dut):
    for i in range(64):
        values=[(i*k+j)&255 for k,j in ((17,1),(23,2),(31,3),(43,4))]
        for name,value in zip(("a","b","c","d"),values):
            getattr(dut,name).value=value
        idx=i%4
        dut.idx.value=idx
        await Timer(2,unit="ns")
        assert int(dut.call_o.value)==values[0]^0x5a
        assert int(dut.literal_o.value)==values[2]
        assert int(dut.dynamic_o.value)==values[idx]
        assert int(dut.repeat_o.value)==(values[0]+3)&255
        assert int(dut.sum_o.value)==sum(values)
