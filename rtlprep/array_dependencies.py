"""Assignment-local array bit coordinates from elaborated slang type strings.

Only explicit fixed dimensions and direct continuous copy assignments.
The existing signal and flat bit graphs are deliberately unchanged.
"""
from collections import Counter, defaultdict
import re
from .constant_indices import evaluate, scope_constants
from .symbols import SignalResolver
from .complex_constructs import location, reference_summary

MAX_DIMENSIONS=4
MAX_WIDTH=1024
MAX_ROWS=2000
MAX_EDGES=16384
MAX_SCAN=50000
MAX_DEPTH=24
DIM=r"\[(\d{1,5}):(\d{1,5})\]"
TYPE=re.compile(r"(logic|bit)((?:"+DIM+r")*)(?:\$((?:"+DIM+r")+))?")

class Unsupported(ValueError):
    pass

def layout(raw):
    """Slang TypePrinter SystemName spelling: logic[P:Q]$[U:V]."""
    if not isinstance(raw,str) or len(raw)>128:
        return None
    m=TYPE.fullmatch(raw)
    if m is None:
        return None
    packed_text,_,_,unpacked_text,_,_=m.groups()[1:]
    packed=tuple((int(a),int(b)) for a,b in re.findall(DIM,packed_text))
    unpacked=tuple((int(a),int(b)) for a,b in re.findall(DIM,unpacked_text or ""))
    if len(packed)+len(unpacked)>MAX_DIMENSIONS:
        return None
    size=1
    for left,right in packed+unpacked:
        if max(left,right)>65535:
            return None
        size*=abs(left-right)+1
        if size>65536:
            return None
    if packed and abs(packed[-1][0]-packed[-1][1])+1>MAX_WIDTH:
        return None
    return m[1],packed,unpacked

def array_type(raw):
    # Identify even unsupported array spellings; never derive positions
    # from this predicate alone.
    return isinstance(raw,str) and ("$[" in raw or raw.count("[")>1)

def layouts(index):
    candidates=defaultdict(set)
    for instance in index["instances"]:
        for port in instance["ports"]:
            candidates[instance["path"]+"."+port["name"]].add(layout(port.get("type")))
    for signal in index["signals"]:
        name=signal.get("path") or signal["instance_path"]+"."+signal["name"]
        candidates[name].add(layout(signal.get("type")))
    return {name:next(iter(values)) for name,values in candidates.items()
            if len(values)==1 and None not in values}

def decompose(expr):
    """Unwrap bounded selection chains, retaining original selector nodes."""
    selections=[]
    for _ in range(MAX_DIMENSIONS+3):
        if not isinstance(expr,dict):
            break
        kind=expr.get("kind")
        if kind=="NamedValue":
            return expr,list(reversed(selections))
        if kind not in ("ElementSelect","RangeSelect"):
            break
        selections.append(expr)
        expr=expr.get("value")
    raise Unsupported("unsupported_selection_chain")

def contains_array(expr):
    # Only root selections/conversions are in scope, not arbitrary operators.
    for _ in range(MAX_DIMENSIONS+3):
        if not isinstance(expr,dict):
            return False
        if array_type(expr.get("type")):
            return True
        kind=expr.get("kind")
        if kind in ("ElementSelect","RangeSelect"):
            expr=expr.get("value")
        elif kind in ("Conversion","SignedConversion"):
            expr=expr.get("operand")
        else:
            return False
    return False

def selector_refs(expr,resolve):
    refs=set()
    for _ in range(MAX_DIMENSIONS+3):
        if not isinstance(expr,dict):
            break
        kind=expr.get("kind")
        if kind in ("Conversion","SignedConversion"):
            expr=expr.get("operand")
            continue
        if kind not in ("ElementSelect","RangeSelect"):
            break
        fields=("selector",) if kind=="ElementSelect" else ("left","right")
        for field in fields:
            refs.update(reference_summary(expr.get(field),resolve)["signal_references"])
        expr=expr.get("value")
    return sorted(refs)

def inside(index,dim):
    return min(dim)<=index<=max(dim)

def index_value(expr,constants,dim):
    value=evaluate(expr,constants)
    if value is None:
        raise Unsupported("dynamic_or_unproven_index")
    if not inside(value,dim):
        raise Unsupported("index_outside_declared_dimension")
    return value

def lane_order(left,right):
    width=abs(left-right)+1
    if width>MAX_WIDTH:
        raise Unsupported("lane_budget_exceeded")
    return list(range(right,left+(1 if left>=right else -1),1 if left>=right else -1))

def coordinates(expr,resolve,declared,constants,*,allow_conversion=False):
    """Return signal, unpacked indices, outer packed indices, LSB-first bits."""
    if not isinstance(expr,dict):
        raise Unsupported("malformed_expression")
    if allow_conversion and expr.get("kind") in ("Conversion","SignedConversion"):
        inner=expr.get("operand")
        outer_type=layout(expr.get("type"))
        inner_type=layout(inner.get("type")) if isinstance(inner,dict) else None
        # One explicit width-preserving integral conversion only.
        if (outer_type is None or inner_type is None or outer_type[0]!=inner_type[0]
                or outer_type[2] or inner_type[2] or len(outer_type[1])>1 or len(inner_type[1])>1):
            raise Unsupported("unproven_conversion")
        width=lambda t: abs(t[1][0][0]-t[1][0][1])+1 if t[1] else 1
        if width(outer_type)!=width(inner_type):
            raise Unsupported("width_changing_conversion")
        result=coordinates(inner,resolve,declared,constants)
        if len(result[3])!=width(outer_type):
            raise Unsupported("conversion_width_mismatch")
        return result
    base,selectors=decompose(expr)
    signal=resolve(base)
    typ=declared.get(signal)
    if signal is None or typ is None or layout(base.get("type"))!=typ:
        raise Unsupported("unproven_declared_layout")
    _,packed,unpacked=typ
    outer=unpacked+packed[:-1]
    if len(selectors)<len(outer):
        raise Unsupported("aggregate_selection_not_supported")
    indices=[]
    for dim,sel in zip(outer,selectors):
        if sel.get("kind")!="ElementSelect":
            raise Unsupported("outer_dimension_requires_element")
        indices.append(index_value(sel.get("selector"),constants,dim))
    remaining=selectors[len(outer):]
    if not packed:
        if remaining:
            raise Unsupported("extra_scalar_selection")
        bits=[0]
    elif not remaining:
        bits=lane_order(*packed[-1])
    elif len(remaining)!=1:
        raise Unsupported("extra_packed_selection")
    else:
        sel=remaining[0]
        if sel.get("kind")=="ElementSelect":
            bits=[index_value(sel.get("selector"),constants,packed[-1])]
        elif sel.get("selectionKind")=="Simple":
            left=index_value(sel.get("left"),constants,packed[-1])
            right=index_value(sel.get("right"),constants,packed[-1])
            if left!=right and (left>right)!=(packed[-1][0]>packed[-1][1]):
                raise Unsupported("range_direction_mismatch")
            bits=lane_order(left,right)
        else:
            raise Unsupported("indexed_part_select_not_supported")
    return signal,indices[:len(unpacked)],indices[len(unpacked):],bits

def expand_assignment(assignment,resolve,declared,constants):
    if (not isinstance(assignment,dict) or assignment.get("kind")!="Assignment"
            or assignment.get("isNonBlocking") is not False
            or "op" in assignment or "timingControl" in assignment):
        raise Unsupported("not_plain_continuous_assignment")
    dest=coordinates(assignment.get("left"),resolve,declared,constants)
    src=coordinates(assignment.get("right"),resolve,declared,constants,allow_conversion=True)
    if len(src[3])!=len(dest[3]):
        raise Unsupported("assignment_width_mismatch")
    return [{"source":src[0],"source_unpacked_indices":src[1],"source_packed_indices":src[2],
             "source_bit":sb,"target":dest[0],"target_unpacked_indices":dest[1],
             "target_packed_indices":dest[2],"target_bit":db}
            for sb,db in zip(src[3],dest[3])]

def build_array_dependencies(ast,*,index):
    resolver=SignalResolver(ast,index)
    declared=layouts(index)
    items=[]
    edges=[]
    visited=0
    truncated=False
    pending=[(ast.get("design",{}).get("members",[]),None,{},0,False)]
    while pending:
        members,owner,inherited,depth,instance_parameters=pending.pop()
        if not isinstance(members,list):
            continue
        if depth>MAX_DEPTH or visited+len(members)>MAX_SCAN:
            truncated=True
            continue
        visited+=len(members)
        constants=scope_constants(members,inherited,instance_parameters=instance_parameters)
        for node in members:
            if not isinstance(node,dict):
                continue
            kind=node.get("kind")
            if kind=="Instance" and isinstance(node.get("body"),dict) and isinstance(node.get("name"),str):
                child=f"{owner}.{node['name']}" if owner else node["name"]
                pending.append((node["body"].get("members",[]),child,{},depth+1,True))
            elif kind in ("GenerateBlock","GenerateBlockArray","Scope") and node.get("isUninstantiated") is not True:
                pending.append((node.get("members",[]),owner,constants,depth+1,False))
            elif kind=="ContinuousAssign" and owner is not None:
                assignment=node.get("assignment")
                if not isinstance(assignment,dict):
                    continue
                lhs,rhs=assignment.get("left"),assignment.get("right")
                if not (contains_array(lhs) or contains_array(rhs)):
                    continue
                if len(items)>=MAX_ROWS:
                    truncated=True
                    break
                resolve=lambda n:resolver.resolve(owner,n)
                row={"instance":owner,"source_location":location(assignment),
                     "coverage":"partial","edge_count":0,
                     "source_selector_references":selector_refs(rhs,resolve),
                     "target_selector_references":selector_refs(lhs,resolve)}
                # Base references remain available for partial rows.
                for side,expr in (("source",rhs),("target",lhs)):
                    try:
                        if side=="source" and isinstance(expr,dict) and expr.get("kind") in ("Conversion","SignedConversion"):
                            expr=expr.get("operand")
                        base,_=decompose(expr)
                        row[side]=resolve(base)
                    except Unsupported:
                        row[side]=None
                items.append(row)
                try:
                    local=expand_assignment(assignment,resolve,declared,constants)
                    if len(edges)+len(local)>MAX_EDGES:
                        truncated=True
                        raise Unsupported("edge_budget_exceeded")
                    edges.extend({**e,"assignment_id":len(items)-1} for e in local)
                    row.update(coverage="array_position_candidates",edge_count=len(local))
                except Unsupported as exc:
                    row["reason"]=str(exc)
        if len(items)>=MAX_ROWS:
            truncated=True
            break
    counts=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"direct_continuous_fixed_array_copy_candidates",
            "items":items,"edges":edges,"counts":{"captured":len(items),
            "supported":counts["array_position_candidates"],"partial":counts["partial"],
            "edges":len(edges),"truncated":truncated},
            "caveat":"Separate unpacked and outer packed coordinates, not flattened offsets. "
                     "No arbitrary expressions, procedural arrays, global writers, functional influence or proof."}
