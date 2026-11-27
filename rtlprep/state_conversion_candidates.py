"""PR118: same-width explicit bit/logic state conversions.

Literal results are expression-relative, not assignments to target bits.
Dynamic candidates require direct exact named endpoints. No graph promotion.
"""
import re
from collections import Counter
from .array_dependencies import Unsupported
from .bit_widths import integral_shape, width
from .capture_audit import audit_capture
from .dynamic_conversion_candidates import at_pointer, endpoint, require
from .residual_audit import exact_links
from .symbols import SignalResolver
from .typed_layout import raw_layouts

MAX_ROWS=2000
MAX_COORDINATES=32768
MAX_WIDTH=64


def domain(raw):
    m=re.match(r"(bit|logic)(?=$|[ \[])",raw) if isinstance(raw,str) else None
    return m[1] if m else None


def shape(raw):
    require(isinstance(raw,str) and re.fullmatch(
        r"(?:bit|logic)(?: signed| unsigned)?(?:\[\d{1,5}:\d{1,5}\])?",raw),
        "unsupported_state_type")
    sh=integral_shape(raw)
    require(sh is not None and width(sh)<=MAX_WIDTH,"unsupported_state_type")
    return sh


def state_map(source,dest):
    require((source,dest) in (("bit","logic"),("logic","bit")),"not_state_transition")
    return {"0":"0","1":"1"} if source=="bit" else {"0":"0","1":"1","x":"0","z":"0"}


def literal_bits(raw,n,source):
    """Strict sized unsigned binary/decimal serialization, LSB first."""
    require(type(n) is int and 1<=n<=MAX_WIDTH,"unsupported_literal_width")
    require(source in ("bit","logic"),"unsupported_state_type")
    m=re.fullmatch(r"([1-9][0-9]?)'([bBdD])([0-9xXzZ]+)",raw) if isinstance(raw,str) and len(raw)<=MAX_WIDTH+5 else None
    require(m is not None and int(m[1])==n,"unproven_state_literal")
    digits=m[3].lower()
    if m[2].lower()=="d":
        require(digits.isdecimal(),"unsupported_decimal_unknown")
        v=int(digits)
        require(v < (1<<n),"state_literal_overflow")
        digits=format(v,f"0{n}b")
    else:
        require(all(b in "01xz" for b in digits) and len(digits)<=n,"unproven_state_literal")
        digits=digits.rjust(n,digits[0] if digits[0] in "xz" else "0")
    require(source=="logic" or all(b in "01" for b in digits),"unknown_in_two_state_literal")
    return list(reversed(digits))


def corroborate(node,n,d,bits):
    if "constant" in node:
        require(literal_bits(node["constant"],n,d)==bits,"state_literal_tag_disagreement")


def expand(node,context,resolve,raw):
    rhs=node.get("right")
    require(isinstance(rhs,dict) and rhs.get("kind")=="Conversion","not_direct_conversion")
    leaf=rhs.get("operand")
    require(isinstance(leaf,dict),"missing_state_operand")
    s,d=domain(leaf.get("type")),domain(rhs.get("type"))
    table=state_map(s,d)
    a,b=shape(leaf.get("type")),shape(rhs.get("type"))
    require(width(a)==width(b) and a[2]==b[2],"state_width_or_signedness_changed")
    n=width(a)
    common={"source_domain":s,"result_domain":d,"width":n,
            "source_type":leaf["type"],"result_type":rhs["type"],
            "state_map":table,"timing":"not_proven","guard_feasibility":"not_proven"}
    if leaf.get("kind")=="IntegerLiteral":
        require(not a[2],"unsupported_signed_literal")
        v=literal_bits(leaf.get("value"),n,s)
        corroborate(leaf,n,s,v)
        converted=[table[x] for x in v]
        corroborate(rhs,n,d,converted)
        return {**common,"family":"literal_expression","source_values_lsb_first":v,
                "result_values_lsb_first":converted,"coordinate_space":"expression_relative",
                "potential_pairs":0,"permanent_constant":"not_inferred"}
    require(leaf.get("kind")=="NamedValue","unsupported_state_operand")
    require(context in ("continuous","AlwaysComb"),"unsupported_assignment_context")
    require(node.get("kind")=="Assignment" and node.get("isNonBlocking") is False
            and node.get("op") is None and node.get("timingControl") is None,
            "not_plain_blocking_assignment")
    lhs=node.get("left")
    require(isinstance(lhs,dict) and node.get("type")==lhs.get("type")==rhs["type"],
            "not_exact_result_conversion")
    require("constant" not in rhs,"constant_tag_outside_dynamic_scope")
    src,dst=endpoint(leaf,resolve,raw),endpoint(lhs,resolve,raw)
    return {**common,"family":"dynamic_statement","source":src,"target":dst,
            "pairs":[{"source_bit":i,"target_bit":j} for i,j in zip(src["bits_lsb_first"],dst["bits_lsb_first"])],
            "potential_pairs":n,"coordinate_space":"declared_signal_bits",
            "relation":"state_transform_candidate","permanent_constant":"not_inferred"}


def audit_state_conversions(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    rows=[]; values=pairs=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        rhs=node.get("right")
        if not isinstance(rhs,dict) or rhs.get("kind")!="Conversion":
            continue
        leaf=rhs.get("operand")
        if not isinstance(leaf,dict):
            continue
        s,d=domain(leaf.get("type")),domain(rhs.get("type"))
        if (s,d) not in (("bit","logic"),("logic","bit")):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("state_conversion_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        row.update(coverage="partial",historical_residual=row["flat_assignment_id"] in residual,
                   source_type=leaf.get("type"),result_type=rhs.get("type"))
        try:
            candidate=expand(node,row["context"],lambda e:resolver.resolve_exact(row["instance"],e),raw)
            if candidate["family"]=="dynamic_statement" and row["flat_assignment_id"] is not None:
                require(candidate["target"]["signal"]==graph["bit_dependency_graph"]["items"][row["flat_assignment_id"]]["target"],
                        "assignment_target_identity_mismatch")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            values+=len(candidate.get("result_values_lsb_first",[])); pairs+=candidate["potential_pairs"]
            if values+pairs>MAX_COORDINATES:
                raise ValueError("state_conversion_coordinate_budget")
            row.update(coverage="state_conversion_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_direct_bit_logic_state_conversion_expressions",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],
                      "roots":len(rows),"supported":len(good),"partial":len(rows)-len(good),
                      "literal_sites":sum(r["candidate"]["family"]=="literal_expression" for r in good),
                      "dynamic_sites":sum(r["candidate"]["family"]=="dynamic_statement" for r in good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "supported_without_flat_id":sum(r["flat_assignment_id"] is None for r in good),
                      "expression_value_positions":values,"potential_pairs":pairs,
                      "stored_coordinates":values+pairs,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Literal values are expression-relative, even in sequential contexts; no target values, effective guards, timing, permanent constants, global influence or RTL equivalence."}
