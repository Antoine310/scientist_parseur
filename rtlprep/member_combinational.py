"""Opt-in statement-local constants and structural logical references.

Reuse the same freshly linked evidence for both opt-in member channels.
Constants are not edges; references are not position copies or influence.
Configuration evidence is attached to the exact operand and occurrence.
"""
from collections import Counter
from copy import deepcopy

from .array_dependencies import Unsupported
from .member_evidence import natural
from .member_occurrences import collect_linked
from .member_positions import layout_for, endpoint, field_info, _build_member_positions
from .local_packed_members import local_types
from .typed_layout import Types, raw_layouts

MAX_RECORDS=32768
CATEGORIES=("local_constant","configuration_constant","logical_reference")


def constant_field(p):
    if "field_coordinates" in p:
        if "field_bit" in p or "target_field" in p:
            raise Unsupported("ambiguous_constant_field_coordinates")
        coord=p["field_coordinates"]
        if not isinstance(coord,list) or not coord or not all(natural(v) for v in coord):
            raise Unsupported("invalid_constant_field_coordinates")
        return p.get("field"),coord
    return field_info(p,"target")


def configuration_proof(row,bit):
    operands=row.get("conditional_operands")
    if not isinstance(operands,list):
        raise Unsupported("missing_configuration_operands")
    matches=[o for o in operands if isinstance(o,dict) and isinstance(o.get("target_bits"),list)
             and bit in o["target_bits"]]
    if len(matches)!=1 or matches[0].get("coverage")!="configuration_constant":
        raise Unsupported("unproven_configuration_operand")
    proof=matches[0].get("proof")
    if not isinstance(proof,dict):
        raise Unsupported("missing_configuration_proof")
    v=proof.get("guard_value")
    params=proof.get("parameters")
    if (type(v) is not int or v not in (0,1)
            or proof.get("selected_branch")!=("left" if v else "right")
            or not isinstance(params,list) or not params):
        raise Unsupported("invalid_configuration_proof")
    seen=set()
    for p in params:
        if (not isinstance(p,dict) or not isinstance(p.get("instance"),str) or not p["instance"]
                or not isinstance(p.get("name"),str) or not p["name"]
                or type(p.get("value")) is not int or p["value"] not in (0,1)):
            raise Unsupported("invalid_configuration_parameter")
        key=(p["instance"],p["name"])
        if key in seen:
            raise Unsupported("duplicate_configuration_parameter")
        seen.add(key)
    return deepcopy(proof)


def _build_combinational(ast,index,graph,envelope,linked):
    if any(linked["counts"][k] for k in ("duplicate_records","candidate_disagreement_groups","mixed_coordinate_groups")):
        raise Unsupported("unresolved_member_candidate_overlap")
    types=Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    locals_=local_types(ast)
    raw=raw_layouts(index)
    nodes=set(graph["nodes"])
    by_row={rid:g for g in linked["occurrences"] for rid in g["row_ids"]}
    rows={r["row_id"]:r["payload"] for r in envelope["rows"]}
    cache={}
    collections={k:[] for k in CATEGORIES}
    count=0
    def get_endpoint(owner,p,side,field,coord):
        sig=p[side]
        if sig not in nodes or sig not in raw:
            raise Unsupported("unproven_endpoint_signal")
        key=(owner,sig)
        if key not in cache:
            cache[key]=layout_for(raw[sig],owner,types,locals_)
        lay=cache[key]
        if lay["kind"]=="packed_vector_coordinates":
            raise Unsupported("unsupported_combinational_endpoint_coordinates")
        return endpoint(sig,raw[sig],lay,p[side+"_bit"],field,coord)
    for r in envelope["records"]:
        category=r["category"]
        if category not in collections:
            continue
        count+=1
        if count>MAX_RECORDS:
            raise Unsupported("member_combinational_channel_budget")
        p=r["payload"]
        occ=by_row[r["row_id"]]
        owner=occ["instance"]
        if occ["context"] not in ("continuous","AlwaysComb"):
            raise Unsupported("unsupported_combinational_context")
        item={"record_id":r["record_id"],"producer":r["producer"],"row_id":r["row_id"],
              "occurrence_ordinal":occ["occurrence_ordinal"],"instance":owner,"context":occ["context"],
              "source_location":deepcopy(occ["source"]),"payload":deepcopy(p)}
        if category=="logical_reference":
            item["source"]=get_endpoint(owner,p,"source",*field_info(p,"source"))
            item["target"]=get_endpoint(owner,p,"target",*field_info(p,"target"))
            item["semantics"]="structural_reference_only"
        else:
            item["target"]=get_endpoint(owner,p,"target",*constant_field(p))
            if type(p.get("value")) is not int or p["value"] not in (0,1) or "source" in p:
                raise Unsupported("invalid_local_constant")
            item["value"]=p["value"]
            item["semantics"]="statement_local_when_executed"
            if category=="configuration_constant":
                item["configuration_proof"]=configuration_proof(rows[r["row_id"]],p["target_bit"])
                item["semantics"]="configuration_local_when_executed"
        collections[category].append(item)
    counts={k:len(v) for k,v in collections.items()}
    counts.update(records=count,occurrences=len({r["occurrence_ordinal"] for v in collections.values() for r in v}),
                  other_candidate_records_not_promoted=len(envelope["records"])-count)
    return {"schema_version":1,"scope":"assignment_local_member_combinational_candidates",
            "collections":collections,"counts":counts,"identity":"same_ast_traversal_only",
            "truncated":False,"design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed",
            "caveat":"Constants apply only when the statement executes; configuration constants only in this elaboration. "
                     "Logical references are structural, not copies or influence. No guard/priority/temporal/global value proof. "
                     "Field identity remains conditional on serialized metadata; no historical graph promotion."}


def build_member_channels(ast,index,graph,*,positions=False,combinational=True,sequential=False):
    envelope,_,linked=collect_linked(ast,index)
    result={}
    if combinational:
        result["member_combinational_candidates"]=_build_combinational(ast,index,graph,envelope,linked)
    if positions:
        result["member_position_candidates"]=_build_member_positions(ast,index,graph,envelope,linked)
    if sequential:
        from .member_sequential import _build_sequential
        result["member_sequential_candidates"]=_build_sequential(ast,index,graph,envelope,linked)
    return result
