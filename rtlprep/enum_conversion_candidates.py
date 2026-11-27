"""PR117: direct package enum encodings and bounded binary casts.

Separate statement-local report; never admit or promote historical graph rows.
"""
import json
import re
from collections import Counter
from .array_dependencies import Unsupported, layouts
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .dynamic_conversion_candidates import at_pointer, require, endpoint
from .enum_member_writes import SYMBOL, enum_for
from .residual_audit import exact_links, reconcile_capture
from .symbols import SignalResolver
from .typed_layout import Types, TOKEN, identity, raw_layouts
from .zero_extended_additions import endpoint as selected_endpoint

MAX_ENUM_WIDTH = 8
MAX_ENUM_VALUES = 256
MAX_ROWS = 2000
MAX_COORDINATES = 32768
MAX_DEPTH = 4
LEAVES = {"NamedValue", "RangeSelect", "ElementSelect"}


def unsigned_width(typ):
    m = re.fullmatch(r"(logic|bit)\[([0-9]{1,2}):0\]", typ) if isinstance(typ,str) else None
    require(m is not None and int(m[2]) < 32, "unsupported_unsigned_encoding_type")
    return int(m[2])+1


def literal(raw, n):
    m = re.fullmatch(r"([1-9][0-9]?)'([bBoOdDhH])([0-9a-fA-F]+)",raw) if isinstance(raw,str) and len(raw)<=64 else None
    require(m is not None and int(m[1])==n,"unproven_enum_literal_width")
    try:
        value=int(m[3],{"b":2,"o":8,"d":10,"h":16}[m[2].lower()])
    except ValueError as exc:
        raise Unsupported("unproven_enum_literal_digits") from exc
    require(0<=value<(1<<n),"enum_encoding_overflow")
    return value


def corroborate(node, value, n):
    if "constant" in node:
        require(literal(node["constant"],n)==value,"enum_folded_disagreement")


def initializer(node, depth=0):
    require(depth<=MAX_DEPTH,"enum_initializer_depth_budget")
    require(isinstance(node,dict),"missing_enum_initializer")
    n=unsigned_width(node.get("type"))
    if node.get("kind")=="IntegerLiteral":
        value=literal(node.get("value"),n)
    elif node.get("kind")=="Conversion":
        value=initializer(node.get("operand"),depth+1)
        # Only nonnegative unsigned, no wrap and no unknown-state behavior.
        require(value < (1<<n),"enum_initializer_truncation")
    else:
        raise Unsupported("unsupported_enum_initializer")
    corroborate(node,value,n)
    return value


def enum_table(enum):
    typ=enum.get("baseType")
    n=unsigned_width(typ)
    require(typ.startswith("logic[") and n<=MAX_ENUM_WIDTH,"unsupported_enum_base")
    members=enum.get("members")
    require(isinstance(members,list) and bool(members),"missing_enum_members")
    require(len(members)<=MAX_ENUM_VALUES,"enum_member_budget")
    table={}; names=set(); addresses=set(); codes=set(); previous=-1
    for entry in members:
        require(isinstance(entry,dict) and entry.get("kind")=="EnumValue","malformed_enum_member")
        addr,name=identity(entry),entry.get("name")
        require(addr is not None and isinstance(name,str) and SYMBOL.fullmatch(addr+" "+name),
                "malformed_enum_member_identity")
        require(addr not in addresses and name not in names,"ambiguous_enum_member")
        if "initializer" in entry:
            init=entry["initializer"]
            require(isinstance(init,dict) and init.get("type")==typ,"enum_initializer_type_disagreement")
            value=initializer(init)
            method="explicit_unsigned_initializer"
        else:
            value=previous+1
            method="implicit_declaration_order"
        require(value<(1<<n),"enum_encoding_overflow")
        require(literal(entry.get("value"),n)==value,"enum_declaration_value_disagreement")
        require(value not in codes,"duplicate_enum_encoding")
        table[addr+" "+name]=(name,value,method)
        names.add(name); addresses.add(addr); codes.add(value); previous=value
    return typ,n,table


def enum_definition(raw, types):
    if not isinstance(raw,str) or not TOKEN.fullmatch(raw):
        return None
    node=types.types.get(raw)
    if isinstance(node,dict) and node.get("kind")=="EnumType":
        return raw,node
    return enum_for(raw,types)


def expand(node, context, types, resolve, raw, declared, constants, *, linked=False):
    require(context in ("continuous","AlwaysComb"),"unsupported_assignment_context")
    require(node.get("kind")=="Assignment" and node.get("isNonBlocking") is False
            and node.get("op") is None and node.get("timingControl") is None,
            "not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    require(isinstance(lhs,dict) and isinstance(rhs,dict) and rhs.get("kind")=="Conversion"
            and node.get("type")==lhs.get("type")==rhs.get("type"),"not_exact_result_conversion")
    leaf=rhs.get("operand")
    require(isinstance(leaf,dict) and leaf.get("kind") in LEAVES,
            "unsupported_direct_enum_leaf")
    source_enum=enum_definition(leaf.get("type"),types)
    target_enum=enum_definition(lhs.get("type"),types)
    require(bool(source_enum)!=bool(target_enum),"unproven_single_enum_endpoint")
    if source_enum:
        token,enum=source_enum
        typ,n,table=enum_table(enum)
        require(leaf.get("kind")=="NamedValue" and resolve(leaf) is None
                and leaf.get("type")==token and leaf.get("symbol") in table,
                "unproven_enum_value_identity")
        require(lhs.get("type")==typ,"enum_result_layout_disagreement")
        dst=endpoint(lhs,resolve,raw)
        name,value,method=table[leaf["symbol"]]
        corroborate(leaf,value,n)
        corroborate(rhs,value,n)
        return {"family":"enum_constant","enum_type":token.split(" ",1)[1],
                "enum_value":name,"encoding_method":method,"target":dst,
                "value":value,"values_lsb_first":[(value>>i)&1 for i in range(n)],
                "potential_pairs":0,"permanent_constant":"not_inferred",
                "guard_feasibility":"not_proven","timing":"not_proven",
                "model_domain":"defined_binary_inputs_only"}
    token,enum=target_enum
    typ,n,table=enum_table(enum)
    require(len(table)==1<<n,"enum_binary_domain_incomplete")
    require("constant" not in rhs and "constant" not in leaf and lhs.get("kind")=="NamedValue" and "constant" not in lhs,
            "unsupported_dynamic_enum_target")
    dst=resolve(lhs)
    require(dst is not None and raw.get(dst)==lhs.get("type"),"unproven_exact_enum_target")
    require(linked,"dynamic_enum_requires_exact_flat_link")
    require(leaf.get("kind")=="RangeSelect" and leaf.get("selectionKind")=="Simple",
            "unsupported_dynamic_enum_source")
    src=selected_endpoint(leaf,resolve,raw,declared,constants)
    require(not src["outer_packed_indices"] and len(src["bits_lsb_first"])==n
            and re.fullmatch(r"logic\[\d{1,5}:\d{1,5}\]",leaf.get("type","")),
            "enum_cast_layout_disagreement")
    # No address-bearing selector AST in the public report.
    src={k:v for k,v in src.items() if k!="selector_proofs"}
    return {"family":"enum_binary_cast","enum_type":token.split(" ",1)[1],
            "target":{"signal":dst,"type":lhs["type"].split(" ",1)[1],
                      "bits_lsb_first":list(range(n))},
            "source":src,"pairs":[{"source_bit":s,"target_bit":i} for i,s in enumerate(src["bits_lsb_first"])],
            "potential_pairs":n,"enum_domain_size":len(table),
            "guard_feasibility":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_enum_conversions(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    constants={i:c for i,_,_,_,c,_ in captured}
    types=Types(ast)
    if types.truncated:
        raise ValueError("package_inventory_budget")
    resolver=SignalResolver(ast,index)
    raw,declared=raw_layouts(index),layouts(index)
    rows=[]; pairs=values=0
    for occurrence in census["items"]:
        node=at_pointer(ast,occurrence["ast_path"])
        rhs=node.get("right")
        if not isinstance(rhs,dict) or rhs.get("kind")!="Conversion":
            continue
        leaf=rhs.get("operand")
        if not isinstance(leaf,dict) or leaf.get("kind") not in LEAVES:
            continue
        if not any(isinstance(t,str) and TOKEN.fullmatch(t) for t in (rhs.get("type"),leaf.get("type"))):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("enum_conversion_row_budget")
        row={k:occurrence[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            if i is not None:
                original,owner,partial=cap[i]
                require(original is node and owner==row["instance"],"capture_identity_disagreement")
                require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],types,lambda e:resolver.resolve_exact(row["instance"],e),
                             raw,declared,constants.get(i,{}),linked=i is not None)
            if i is not None:
                require(candidate["target"]["signal"]==graph["bit_dependency_graph"]["items"][i]["target"],
                        "assignment_target_identity_mismatch")
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"]=str(exc)
        else:
            pairs+=candidate["potential_pairs"]; values+=len(candidate.get("values_lsb_first",[]))
            if pairs+values>MAX_COORDINATES:
                raise ValueError("enum_coordinate_budget")
            row.update(coverage="enum_conversion_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_direct_package_enum_conversions",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],
                      "roots":len(rows),"supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "supported_without_flat_id":sum(r["flat_assignment_id"] is None for r in good),
                      "potential_pairs":pairs,"value_records":values,"stored_coordinates":pairs+values,"truncated":False},
            "items":rows,
            "partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Binary statement-local values and positional candidates; no X/Z, guards, reachability, timing, permanent constants or RTL equivalence."}
