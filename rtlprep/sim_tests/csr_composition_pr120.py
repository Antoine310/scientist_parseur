import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def csr_binary_oracle(dut):
    for address in range(4096):
        for enable in range(2):
            for inhibition in (0,0xffffffff):
                dut.csr_addr_i.value=address
                dut.csr_we_int.value=enable
                dut.inhibit.value=inhibition
                await Timer(1,unit="ns")
                lo=(1 << (address-0xb00)) if enable and 0xb00<=address<0xb20 else 0
                hi=(1 << (address-0xb80)) if enable and 0xb80<=address<0xba0 else 0
                assert int(dut.mhpmcounter_write_lower.value)==lo
                assert int(dut.mhpmcounter_write_upper.value)==(hi & ~inhibition)
