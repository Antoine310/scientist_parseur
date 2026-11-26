import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def aggregate_layout(dut):
    for v in range(256):
        dut.data.value = v
        await Timer(2, unit="ns")
        assert int(dut.concat_hi.value) == v >> 5, f"PR78_CONCAT_HIGH v={v}"
        assert int(dut.concat_lo.value) == v & 31, f"PR78_CONCAT_LOW v={v}"
        assert int(dut.struct_hi.value) == v >> 5
        assert int(dut.struct_lo.value) == v & 31
        assert int(dut.union_hi.value) == v >> 5
