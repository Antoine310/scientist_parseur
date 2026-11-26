"""Link fresh experimental evidence to assignment traversal occurrences.

The ordinal is scoped to one in-memory elaborated AST and the version of
assignment_sites. Never match by source line, or reuse across elaborations.
Exact-record grouping is not semantic equivalence or a graph promotion.
"""
from collections import defaultdict
import json

from .aggregate_layout import assignment_sites, member_sites
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .member_evidence import PRODUCERS, normalize, natural

MAX_OCCURRENCES=100000


def occurrence_inventory(ast):
    inspect_ast(ast)
    out={}
    for ordinal,(owner,context,node) in enumerate(assignment_sites(ast)):
        if ordinal>=MAX_OCCURRENCES:
            raise Unsupported("occurrence_inventory_budget")
        if not (member_sites(node.get("left")) or member_sites(node.get("right"))):
            continue
        out[ordinal]={"occurrence_ordinal":ordinal,"instance":owner,"context":context,
                      "source":{"file":node.get("source_file_start") or node.get("source_file"),
                                "line":node.get("source_line_start") or node.get("source_line")},
                      "lhs_kind":(node.get("left") or {}).get("kind"),
                      "rhs_kind":(node.get("right") or {}).get("kind")}
    return out


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)


def link(ast,envelope):
    """Link an envelope freshly produced from this exact AST, not external JSON."""
    inventory=occurrence_inventory(ast)
    groups={n:{**v,"row_ids":[],"record_ids":[]} for n,v in inventory.items()}
    row_to_occ={}
    seen=set()
    for row in envelope["rows"]:
        payload=row["payload"]
        n=payload.get("occurrence_ordinal")
        if not natural(n) or n not in inventory:
            raise Unsupported("unproven_occurrence_ordinal")
        if any(payload.get(k)!=inventory[n][k] for k in ("instance","context","source")):
            raise Unsupported("occurrence_metadata_disagreement")
        key=(row["producer"],n)
        rid=row["row_id"]
        if key in seen or rid in row_to_occ:
            raise Unsupported("duplicate_producer_occurrence")
        seen.add(key)
        row_to_occ[rid]=n
        groups[n]["row_ids"].append(rid)
    if {n for producer,n in seen if producer=="pr79"}!=set(inventory):
        raise Unsupported("member_census_disagreement")

    # Preserve all original record IDs and payloads. Exact duplicates are
    # grouped only within an occurrence, not removed from the envelope.
    exact=defaultdict(list)
    lanes=defaultdict(list)
    coordinate_kinds=defaultdict(set)
    record_ids=set()
    for record in envelope["records"]:
        rid=record["record_id"]
        if rid in record_ids or record["row_id"] not in row_to_occ:
            raise Unsupported("invalid_linked_record")
        record_ids.add(rid)
        n=row_to_occ[record["row_id"]]
        p=record["payload"]
        groups[n]["record_ids"].append(rid)
        raw={k:v for k,v in p.items() if k!="site_id"}
        exact[(n,record["category"],canonical(raw))].append(rid)
        if "target_packed_offset" in p:
            coord="packed_offset"
            bit=p["target_packed_offset"]
        else:
            coord="producer_target_bit"
            bit=p["target_bit"]
        key=(n,p["target"])
        coordinate_kinds[key].add(coord)
        # Logical references may legitimately share a destination lane.
        # They are references, not claims of equal value.
        lanes[(n,p["target"],coord,bit)].append(record)
    duplicates=[{"occurrence_ordinal":n,"record_ids":ids}
                for (n,_,_),ids in exact.items() if len(ids)>1]
    overlaps,conflicts=[],[]
    for (n,target,coord,bit),records in lanes.items():
        nonlogical=[r for r in records if r["category"]!="logical_reference"]
        logical=[r for r in records if r["category"]=="logical_reference"]
        if len(nonlogical)<2 and not (nonlogical and logical):
            continue
        distinct={canonical({"category":r["category"],
                   "payload":{k:v for k,v in r["payload"].items() if k!="site_id"}}) for r in records}
        if len(distinct)<2:
            continue
        item={"occurrence_ordinal":n,"target":target,"coordinate_kind":coord,"position":bit,
              "record_ids":[r["record_id"] for r in records]}
        overlaps.append(item)
        # Conservative disagreement of candidate claims, not proof of RTL conflict.
        signatures=set()
        for r in nonlogical:
            p=r["payload"]
            signatures.add((r["category"],p.get("source"),p.get("source_bit"),p.get("value")))
        if len(signatures)>1 or (logical and nonlogical):
            conflicts.append(item)
    mixed=[{"occurrence_ordinal":n,"target":t,"coordinate_kinds":sorted(k)}
           for (n,t),k in coordinate_kinds.items() if len(k)>1]
    return {"schema_version":1,"scope":"member_occurrence_linkage",
            "identity":"assignment_sites_ordinal_same_ast_only",
            "counts":{"occurrences":len(groups),"producer_rows":len(row_to_occ),
                      "candidate_records":len(record_ids),"distinct_exact_records":len(exact),
                      "duplicate_records":len(record_ids)-len(exact),
                      "overlap_groups":len(overlaps),"candidate_disagreement_groups":len(conflicts),
                      "mixed_coordinate_groups":len(mixed),
                      "occurrences_without_records":sum(not g["record_ids"] for g in groups.values())},
            "occurrences":list(groups.values()),"exact_duplicate_groups":duplicates,
            "overlap_groups":overlaps,"candidate_disagreement_groups":conflicts,
            "mixed_coordinate_groups":mixed,
            "graph_integration":"not_performed","functional_influence":"not_proven",
            "formal_proof":"not_performed","design_coverage":"not_measured",
            "caveat":"Ordinal valid only in this traversal of the same elaboration. Exact duplicates use raw payload "
                     "excluding local site_id; no semantic coordinate conversion or global deduplication. "
                     "Overlap/disagreement diagnostics are candidate-level, not proof of circuit conflict."}


def collect_linked(ast,index):
    reports={name:audit(ast,index,include_occurrence=True) for name,audit in PRODUCERS}
    envelope=normalize(reports)
    return envelope,reports,link(ast,envelope)
