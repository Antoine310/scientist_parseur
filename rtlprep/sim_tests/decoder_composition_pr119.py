import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def decoder_binary_oracle(dut):
    for a in range(128):
        for b in range(128):
            addr_a, en_a = a & 63, a >> 6
            addr_b, en_b = b & 63, b >> 6
            dut.waddr_a.value=addr_a
            dut.waddr_b.value=addr_b
            dut.we_a_i.value=en_a
            dut.we_b_i.value=en_b
            await Timer(1,unit="ns")
            expected_a=(1 << addr_a) if en_a and addr_a<32 else 0
            expected_b=(1 << addr_b) if en_b and addr_b<32 else 0
            assert int(dut.we_a_dec.value)==expected_a
            assert int(dut.we_b_dec.value)==expected_b
