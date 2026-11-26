import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def enum_field_positions(dut):
    for choose in range(2):
        for marker in range(2):
            dut.choose.value = choose
            dut.marker.value = marker
            await Timer(2, unit="ns")
            expected = (marker << 3) | ((2 if choose else 1) << 1) | (1-marker)
            assert int(dut.packed_o.value) == expected
