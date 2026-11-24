import copy
import pytest
from scripts.run_scalability_pr55 import generate_pipeline, validate_sizes, oracle, summarize, TOP

def test_generated_pipeline():
    text=generate_pipeline(3)
    assert text==generate_pipeline(3)
    assert text.count("scale_stage55 stage_")==3
    assert "stage_0(.clk(clk), .d(data_i), .q(link_0))" in text
    assert "stage_1(.clk(clk), .d(link_0), .q(link_1))" in text
    assert "stage_2(.clk(clk), .d(link_1), .q(result_o))" in text

def test_one_stage():
    text=generate_pipeline(1)
    assert "stage_0(.clk(clk), .d(data_i), .q(result_o))" in text
    assert "link_" not in text

@pytest.mark.parametrize("sizes",[[],[0],[1025],[4,4],[8,2],[True],list(range(1,10))])
def test_size_bounds(sizes):
    with pytest.raises(ValueError):
        validate_sizes(sizes)

def sample():
    return {"status":"passed","stages":8,"source_fingerprint":"p","source_sha256":["a"],
            "semantic_metrics":{"graph_counts":{"nodes":5}},"fixture_oracle":{"instances":9},
            "seconds":{"pipeline_total":2.0},"peak_rss_kib":{"python_worker":100},
            "bytes":{"rtl_dependencies.json":40}}

def test_distribution():
    a,b,c=sample(),sample(),sample()
    b["seconds"]["pipeline_total"]=3.0
    c["seconds"]["pipeline_total"]=7.0
    s=summarize([a,b,c])
    assert s["seconds"]["pipeline_total"]=={"min":2.0,"median":3.0,"max":7.0}
    assert s["repetitions"]==3

@pytest.mark.parametrize("key",["source_fingerprint","source_sha256","semantic_metrics","fixture_oracle"])
def test_semantic_drift_rejected(key):
    a,b=sample(),sample()
    b[key]=None
    with pytest.raises(ValueError,match="nonreproducible"):
        summarize([a,b])

def test_failed_sample_rejected():
    a=sample()
    a["status"]="failed"
    with pytest.raises(ValueError):
        summarize([a])

def one_stage_graph():
    p=TOP+".stage_0"
    index={"instances":[{"path":TOP},{"path":p}]}
    edges=[(TOP+".clk",p+".clk","port_input",False),
           (TOP+".data_i",p+".d","port_input",False),
           (p+".q",TOP+".result_o","port_output",False),
           (p+".d",p+".perm","data",False),(p+".perm",p+".q","data",True)]
    graph={"edges":[{"source":s,"target":t,"kind":k,"sequential":seq} for s,t,k,seq in edges],
           "bit_dependency_graph":{"edges":[{"source":p+".d","source_bit":b,
              "target":p+".perm","target_bit":(b+4)%8} for b in range(8)],"counts":{"truncated":False}},
           "register_flow":{"counts":{"truncated":False}}}
    return index,graph

def test_oracle_exact_positions():
    idx,g=one_stage_graph()
    r=oracle(idx,g,1)
    assert r["matched_signal_links"]==5 and r["matched_bit_positions"]==8

@pytest.mark.parametrize("mode",["instance","signal_link","bit_missing","bit_wrong","bit_duplicate","flow_truncated"])
def test_oracle_fails_on_corruption(mode):
    idx,g=one_stage_graph()
    if mode=="instance":
        idx["instances"].pop()
    elif mode=="signal_link":
        g["edges"].pop()
    elif mode=="bit_missing":
        g["bit_dependency_graph"]["edges"].pop()
    elif mode=="bit_wrong":
        g["bit_dependency_graph"]["edges"][0]["target_bit"]=0
    elif mode=="bit_duplicate":
        g["bit_dependency_graph"]["edges"].append(copy.deepcopy(g["bit_dependency_graph"]["edges"][0]))
    else:
        g["register_flow"]["counts"]["truncated"]=True
    with pytest.raises(ValueError):
        oracle(idx,g,1)
