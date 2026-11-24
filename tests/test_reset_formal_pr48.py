import pytest
from scripts.run_reset_formal_pr48 import config, verdict

@pytest.mark.parametrize("mode,status,rc,traces,want",[
    ("prove","PASS",0,[],"passed"),
    ("prove","UNKNOWN",0,[],"failed"),
    ("prove","PASS",1,[],"failed"),
    ("cover","PASS",0,["trace.vcd"],"passed"),
    ("cover","PASS",0,[],"failed"),
    ("bmc","FAIL",2,["trace.vcd"],"expected_counterexample"),
    ("bmc","ERROR",1,["trace.vcd"],"failed"),
    ("bmc","FAIL",2,[],"failed"),
    ("bmc","PASS",0,[],"failed"),
])
def test_verdict(mode,status,rc,traces,want):
    assert verdict(mode,status,rc,traces)==want

def test_config_separate_frontends():
    names=["ras.sv","probe.sv","properties.sv"]
    text=config("prove",names,"ras_formal_properties",True,True)
    assert "plugin -i slang\nread_slang --top ras_formal_probe ras.sv probe.sv" in text
    assert "read -formal -sv properties.sv" in text
    assert "multiclock on" in text
    assert "smtbmc z3" in text

def test_invalid_mode():
    with pytest.raises(ValueError):
        config("invalid",[],"top")
