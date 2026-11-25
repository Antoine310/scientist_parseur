import pytest
from scripts.cv32e40p_pr65 import (TOP, SOURCES, CORE_PINS, MANIFEST, CLOCK_GATE,
    CONFIG, INSTANCE_MODULES, INPUTS, OUTPUTS, LABELS, PATHS, check_manifest)
from scripts.cv32e40p_pr63 import EXTRA_BLOBS
from scripts.run_cv32e40p_core_pr65 import expected_instances, check_structure, check_config, score_core
from scripts.rtl_fixtures import load_lock

def manifest_text():
    prefix="${DESIGN_RTL_DIR}/"
    return "\n".join([prefix+p[4:] for p in SOURCES[:-1]]+
                     [prefix+"cv32e40p_top.sv",prefix+"../"+CLOCK_GATE])

def test_source_inventory():
    pins=next(e["blobs"] for e in load_lock() if e["repository"]=="openhwfoundation/cv32e40p")
    assert len(pins)==6 and len(EXTRA_BLOBS)==6 and len(CORE_PINS)==17
    assert not (set(pins)&set(EXTRA_BLOBS) or set(pins)&set(CORE_PINS) or set(EXTRA_BLOBS)&set(CORE_PINS))
    assert len(SOURCES)==28 and len(set(SOURCES))==28
    assert set(SOURCES)|{MANIFEST}==set(pins)|set(EXTRA_BLOBS)|set(CORE_PINS)

def test_manifest_order():
    assert check_manifest(manifest_text())==SOURCES

@pytest.mark.parametrize("mode",["missing","reorder","extra","clock"])
def test_manifest_mismatch(mode):
    lines=manifest_text().splitlines()
    if mode=="missing":
        del lines[3]
    elif mode=="reorder":
        lines[0],lines[1]=lines[1],lines[0]
    elif mode=="extra":
        lines.insert(3,"${DESIGN_RTL_DIR}/unexpected.sv")
    else:
        lines.pop()
    with pytest.raises(ValueError,match="inventory"):
        check_manifest("\n".join(lines))

def test_hierarchy_inventory():
    expected=expected_instances()
    assert len(expected)==24 and len(set(expected.values()))==23
    assert expected[TOP]=="cv32e40p_core"
    for name in expected:
        if name!=TOP:
            assert name.rsplit(".",1)[0] in expected

def structure():
    instances=[{"path":p,"module":m,"ports":[]} for p,m in expected_instances().items()]
    top=next(i for i in instances if i["path"]==TOP)
    top["ports"]=[{"name":p,"direction":d} for names,d in ((INPUTS,"In"),(OUTPUTS,"Out")) for p in names]
    return {"top":TOP,"nodes":["a","b"],"edges":[{"source":"a","target":"b"}]}, {"top":TOP,"instances":instances}

def test_structure_valid():
    g,i=structure()
    assert check_structure(g,i)==expected_instances()

@pytest.mark.parametrize("mode",["missing_instance","wrong_module","duplicate_instance","wrong_direction","dangling_edge","wrong_top"])
def test_structure_invalid(mode):
    g,i=structure()
    if mode=="missing_instance":
        i["instances"].pop()
    elif mode=="wrong_module":
        i["instances"][-1]["module"]="wrong"
    elif mode=="duplicate_instance":
        i["instances"].append(i["instances"][-1])
    elif mode=="wrong_direction":
        i["instances"][0]["ports"][0]["direction"]="Out"
    elif mode=="dangling_edge":
        g["edges"][0]["target"]="c"
    else:
        g["top"]="wrong"
    with pytest.raises(ValueError):
        check_structure(g,i)

def config_ast():
    return {"design":{"members":[{"kind":"Instance","name":TOP,"body":{"members":[
        {"kind":"Parameter","name":k,"isPort":True,"value":str(v)} for k,v in CONFIG.items()
    ]}}]}}

def test_config_actual_values():
    assert check_config(config_ast())==CONFIG

@pytest.mark.parametrize("mode",["changed","missing","not_port"])
def test_config_reject(mode):
    a=config_ast()
    members=a["design"]["members"][0]["body"]["members"]
    if mode=="changed":
        members[0]["value"]="1"
    elif mode=="missing":
        members.pop()
    else:
        members[0]["isPort"]=False
    with pytest.raises(ValueError,match="configuration"):
        check_config(a)

def test_labels():
    assert len(LABELS)==47 and sum(r["label"]=="positive" for r in LABELS)==39
    assert len({(r["source"],r["target"],r["kind"],r["sequential"]) for r in LABELS})==47
    assert all(r["line"]>0 and r["note"] for r in LABELS)
    assert len(PATHS)==7

def test_scoring_retains_missing_labels():
    nodes={TOP+"."+r[k] for r in LABELS for k in ("source","target")}
    rows=[r for r in LABELS if r["label"]=="positive"]
    edges=[{**r,"source":TOP+"."+r["source"],"target":TOP+"."+r["target"]} for r in rows[1:]]
    score=score_core({"nodes":sorted(nodes),"edges":edges})
    assert (score["tp"],score["fn"],score["fp"],score["tn"])==(38,1,0,8)
