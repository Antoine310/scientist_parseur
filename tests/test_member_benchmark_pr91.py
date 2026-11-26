import copy
import pytest
from scripts import run_member_benchmark_pr91 as m

def flat_graph():
    rows=[{"assignment_id":i,"target":"top.a","source_location":{"line":i},
           "coverage":"partial" if i else "assignment_local_position_candidates","reason":"opaque"} for i in range(4)]
    g={"bit_dependency_graph":{"items":rows,"counts":{"assignments":4,"supported":1,"partial":3,"truncated":False}}}
    for k in m.LINKED_CHANNELS:
        g[k]={"items":[],"counts":{"truncated":False}}
    for k,i in zip(m.LINKED_CHANNELS,(1,1,2,0,2,1)):
        g[k]["items"].append({**rows[i],"flat_assignment_id":i,"coverage":"candidate"})
    return g

def test_flat_union_not_sum():
    g=flat_graph()
    before=copy.deepcopy(g)
    r=m.reconcile_flat(g)
    assert r["flat_supported"]==1 and r["linked_partial_ids"]==2
    assert r["minimum_combined_supported"]==3 and r["remaining_without_linked_support"]==1
    assert r["remaining_reasons"]=={"opaque":1}
    assert not r["member_occurrences_added"] and g==before

@pytest.mark.parametrize("mode",["truncated","count","id","linked_id","target","location","channel_truncated"])
def test_bad_flat_inventory(mode):
    g=flat_graph()
    flat=g["bit_dependency_graph"]
    ch=g[m.LINKED_CHANNELS[0]]
    if mode=="truncated": flat["counts"]["truncated"]=True
    elif mode=="count": flat["counts"]["supported"]=2
    elif mode=="id": flat["items"][0]["assignment_id"]=7
    elif mode=="linked_id": ch["items"][0]["flat_assignment_id"]=True
    elif mode=="target": ch["items"][0]["target"]="wrong"
    elif mode=="location": ch["items"][0]["source_location"]={"line":99}
    else: ch["counts"]["truncated"]=True
    with pytest.raises(ValueError):
        m.reconcile_flat(g)

def evidence():
    categories={c:[] for c in m.CATEGORIES}
    g={m.CHANNELS[0]:{"items":categories["position"]},
       m.CHANNELS[1]:{"collections":{k:categories[k] for k in ("local_constant","logical_reference","configuration_constant")}},
       m.CHANNELS[2]:{"collections":{k:categories[k] for k in ("nba_sampled","nba_constant")}}}
    e={"records":[],"rows":[{}],"counts":{k:1 for k in categories}}
    l={"occurrences":[{"row_ids":["r"],"occurrence_ordinal":9,"instance":"top","context":"AlwaysFF","source":{"line":5}}]}
    for i,(category,items) in enumerate(categories.items()):
        r={"record_id":str(i),"producer":"p","row_id":"r","payload":{"site_id":0,"value":i}}
        e["records"].append({**copy.deepcopy(r),"category":category})
        items.append({**r,"occurrence_ordinal":9,"instance":"top","context":"AlwaysFF","source_location":{"line":5}})
    return g,e,l

def test_exact_reconciliation():
    g,e,l=evidence()
    r=m.reconcile_members(g,e,l)
    assert r["published_records"]==6 and r["member_occurrences"]==1
    assert r["historical_flat_id_mapping"]=="not_established"

@pytest.mark.parametrize("mode",["missing","duplicate","unknown","payload","category","producer","ordinal","location","count","duplicate_inventory"])
def test_refuse_member_mismatch(mode):
    g,e,l=evidence()
    items=g[m.CHANNELS[0]]["items"]
    if mode=="missing": items.clear()
    elif mode=="duplicate": items.append(copy.deepcopy(items[0]))
    elif mode=="unknown": items[0]["record_id"]="unknown"
    elif mode=="payload": items[0]["payload"]["value"]=99
    elif mode=="category": e["records"][0]["category"]="nba_sampled"
    elif mode=="producer": items[0]["producer"]="other"
    elif mode=="ordinal": items[0]["occurrence_ordinal"]=10
    elif mode=="location": items[0]["source_location"]={"line":8}
    elif mode=="count": e["counts"]["position"]=2
    else: e["records"].append(copy.deepcopy(e["records"][0]))
    with pytest.raises(ValueError):
        m.reconcile_members(g,e,l)

def test_paired_delta_not_delta_of_medians():
    samples=[{"baseline":dict.fromkeys(m.METRICS,a),"all_channels":dict.fromkeys(m.METRICS,b)}
             for a,b in ((1,10),(10,11),(100,100))]
    r=m.paired_summary(samples)[m.METRICS[0]]
    assert r["paired_delta"]=={"min":0,"median":1,"max":9}
    assert r["baseline"]["median"]==10 and r["all_channels"]["median"]==11

def test_historical_digest_ignores_only_documented_fields():
    g={"nodes":["a"],"analysis_limits":{}}
    assert m.historical_digest(g)==m.historical_digest({**g,m.CHANNELS[0]:{"items":[1]}})
    assert m.historical_digest(g)!=m.historical_digest({**g,"nodes":["b"]})

def test_empty_benchmark():
    with pytest.raises(ValueError):
        m.paired_summary([])


def test_vmhwm_is_not_current_rss():
    assert m.parse_vmhwm("Name:\tpython\nVmHWM:\t12345 kB\nVmRSS:\t10000 kB\n")==12345

@pytest.mark.parametrize("status",["VmRSS: 100 kB","VmHWM: 0 kB","VmHWM: -2 kB",
    "VmHWM: 5 MB","VmHWM: NaN kB","VmHWM: 12 kB\nVmHWM: 13 kB"])
def test_refuse_invalid_vmhwm(status):
    with pytest.raises(ValueError):
        m.parse_vmhwm(status)

def test_current_exec_vmhwm(monkeypatch):
    from pathlib import Path
    def read(self,**kwargs):
        assert str(self)=="/proc/self/status"
        return "VmHWM: 9876 kB\nVmRSS: 4321 kB\n"
    monkeypatch.setattr(Path,"read_text",read)
    assert m.peak_rss_kib()==9876
