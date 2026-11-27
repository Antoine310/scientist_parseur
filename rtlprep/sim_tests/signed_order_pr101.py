import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def signed_order_fixture(dut):
    for mode in range(2):
        dut.mode.value=mode|2
        for a in range(256):
            dut.a.value=a|256
            for b in range(256):
                dut.b.value=b|256
                await Timer(1,unit="ns")
                x=a-256 if mode and a>=128 else a
                y=b-256 if mode and b>=128 else b
                assert int(dut.greater.value)==int(x>y)
