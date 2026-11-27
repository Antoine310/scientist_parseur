import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def scalar_concat_fixture(dut):
    dut.clk.value=0
    async def tick(reset,bit,expected):
        dut.rst.value=reset
        dut.serial_in.value=bit
        dut.clk.value=0
        await Timer(1,unit="ns")
        dut.clk.value=1
        await Timer(1,unit="ns")
        assert (int(dut.ck.value),int(dut.qq.value),int(dut.q.value))==expected
    for old in range(8):
        for reset in range(2):
            for bit in range(2):
                state=(0,0,0)
                await tick(1,0,state)
                for shift in (2,1,0):
                    inp=(old>>shift)&1
                    state=(state[1],state[2],inp)
                    await tick(0,inp,state)
                assert state==((old>>2)&1,(old>>1)&1,old&1)
                await tick(reset,bit,(0,0,0) if reset else (state[1],state[2],bit))
