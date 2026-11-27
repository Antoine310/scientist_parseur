import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def independent_scope_fixture(dut):
    dut.clk.value=0
    def oracle(data):
        return ((data>>2)&1,data>>4,(data>>3)&1,data&15)
    async def tick(data,en,expected):
        dut.clk.value=0
        dut.data.value=data
        dut.en.value=en
        await Timer(1,unit="ns")
        dut.clk.value=1
        await Timer(1,unit="ns")
        assert (int(dut.flag_a.value),int(dut.word_a.value),
                int(dut.flag_b.value),int(dut.word_b.value))==expected
    for data in range(256):
        old=data^255
        await tick(old,1,oracle(old))
        await tick(data,0,oracle(old))
        await tick(data,1,oracle(data))
