"""Assignment-local syntactic bitwise influence candidates, never copies.

A lane contains the union of runtime leaf coordinates, not a Boolean
derivative or a value proof. Masking/cancellation may make candidates
infeasible. Keep control dependencies and temporal semantics separate.
"""
from collections import Counter
from .array_dependencies import layout, layouts, Unsupported, index_value
from .packed_coordinates import selected
from .bit_widths import integral_shape, width
from .bit_width_literals import literal_width
from .constant_indices import evaluate
from .symbols import SignalResolver

MAX_ROWS=2000
MAX_EDGES=16384
MAX_WIDTH=1024
MAX_DEPTH=12
MAX_NODES=256
MAX_ROW_PAIRS=8192
BINARY=frozenset(("BinaryAnd","BinaryOr","BinaryXor","BinaryXnor"))
REDUCTION=frozenset(("BitwiseAnd","BitwiseOr","BitwiseXor","BitwiseNand","BitwiseNor","BitwiseXnor"))
UNARY=REDUCTION|{"BitwiseNot"}

def has_operator(expr):
    # Scan bounded expression children, not arbitrary metadata.
    pending=[(expr,0)]
    visited=0
    while pending:
        node,depth=pending.pop()
        visited+=1
        if visited>MAX_NODES or depth>MAX_DEPTH:
            raise Unsupported("operator_scan_budget")
        if not isinstance(node,dict):
            continue
        kind=node.get("kind")
        if ((kind=="BinaryOp" and node.get("op") in BINARY)
                or (kind=="UnaryOp" and node.get("op") in UNARY)):
            return True
        for key in ("left","right","operand","concat","operands","conditions","trueExpr","falseExpr"):
            value=node.get(key)
            if isinstance(value,dict):
                pending.append((value,depth+1))
            elif isinstance(value,list):
                if len(value)>MAX_NODES:
                    raise Unsupported("operator_scan_budget")
                pending.extend((v,depth+1) for v in value)
    return False

def shape(expr):
    if not isinstance(expr,dict):
        raise Unsupported("malformed_expression")
    raw=expr.get("type")
    explicit=layout(raw)
    if explicit is not None and not explicit[2] and len(explicit[1])<=1:
        n=abs(explicit[1][0][0]-explicit[1][0][1])+1 if explicit[1] else 1
        if not 1<=n<=MAX_WIDTH:
            raise Unsupported("lane_budget_exceeded")
        return n,explicit[0]=="logic"
    typ=integral_shape(raw)
    if typ is None:
        raise Unsupported("unproven_integral_type")
    return width(typ),typ[3]

def merge(left,right):
    if len(left)+len(right)>2*MAX_ROW_PAIRS:
        raise Unsupported("row_pair_budget")
    result=left|right
    if len(result)>MAX_ROW_PAIRS:
        raise Unsupported("row_pair_budget")
    return result

def checked(lanes,n):
    if len(lanes)!=n:
        raise Unsupported("expression_width_mismatch")
    if sum(len(x) for x in lanes)>MAX_ROW_PAIRS:
        raise Unsupported("row_pair_budget")
    return lanes

def expression(expr,resolve,declared,constants,ops,budget,depth=0):
    budget[0]-=1
    if budget[0]<0 or depth>MAX_DEPTH:
        raise Unsupported("expression_traversal_budget")
    n,state=shape(expr)
    kind=expr.get("kind")
    op=expr.get("op")
    def child(v):
        return expression(v,resolve,declared,constants,ops,budget,depth+1)
    if kind in ("NamedValue","ElementSelect","RangeSelect"):
        loc,base=selected(expr,resolve,declared,constants)
        if (base=="logic")!=state:
            raise Unsupported("selection_state_mismatch")
        return checked([{(loc[0],tuple(loc[2]),b)} for b in loc[3]],n)
    if kind in ("IntegerLiteral","UnbasedUnsizedIntegerLiteral"):
        if literal_width(expr)!=n:
            raise Unsupported("unproven_literal_width")
        return [set() for _ in range(n)]
    if kind=="Conversion":
        operand=expr.get("operand")
        m,operand_state=shape(operand)
        if m!=n:
            raise Unsupported("conversion_width_or_state_change")
        lanes=child(operand)
        if operand_state!=state and any(lanes):
            raise Unsupported("conversion_width_or_state_change")
        return checked(lanes,n)
    if kind=="Concatenation":
        parts=expr.get("operands")
        if not isinstance(parts,list) or not 1<=len(parts)<=32:
            raise Unsupported("concat_operand_budget")
        lanes=[]
        for part in reversed(parts):
            lanes.extend(child(part))
            if len(lanes)>n:
                raise Unsupported("expression_width_mismatch")
        return checked(lanes,n)
    if kind=="Replication":
        count=evaluate(expr.get("count"),constants)
        concat=expr.get("concat")
        if count is None or not 1<=count<=64:
            raise Unsupported("replication_count_unproven")
        part=child(concat)
        if len(part)*count!=n or sum(len(x) for x in part)*count>MAX_ROW_PAIRS:
            raise Unsupported("replication_width_or_pair_budget")
        return checked(part*count,n)
    if kind=="BinaryOp" and op in BINARY:
        left,right=expr.get("left"),expr.get("right")
        if shape(left)!=(n,state) or shape(right)!=(n,state):
            raise Unsupported("bitwise_operand_width_or_state_mismatch")
        a,b=child(left),child(right)
        ops.add(op)
        return checked([merge(x,y) for x,y in zip(a,b)],n)
    if kind=="UnaryOp" and op in UNARY:
        operand=expr.get("operand")
        m,source_state=shape(operand)
        if source_state!=state:
            raise Unsupported("unary_state_mismatch")
        lanes=child(operand)
        ops.add(op)
        if op=="BitwiseNot":
            if m!=n:
                raise Unsupported("unary_width_mismatch")
            return checked(lanes,n)
        if n!=1:
            raise Unsupported("reduction_result_not_scalar")
        result=set()
        for lane in lanes:
            result=merge(result,lane)
        return checked([result],1)
    raise Unsupported("unsupported_expression_"+str(kind)[:64]+("_"+str(op)[:48] if op else ""))

def expand(node,resolve,declared,constants):
    if (node.get("kind")!="Assignment" or type(node.get("isNonBlocking")) is not bool
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    dst,base=selected(lhs,resolve,declared,constants)
    n,state=shape(lhs)
    if (layout(node.get("type"))!=layout(lhs.get("type")) or len(dst[3])!=n
            or shape(rhs)!=(n,state)):
        raise Unsupported("assignment_type_or_width_mismatch")
    ops=set()
    lanes=expression(rhs,resolve,declared,constants,ops,[MAX_NODES])
    if not ops:
        raise Unsupported("no_supported_operator")
    edges=[]
    fixed=[]
    for b,leaves in zip(dst[3],lanes):
        dest={"target":dst[0],"target_packed_indices":dst[2],"target_bit":b}
        if not leaves:
            fixed.append(dest)
        for src,coords,sbit in sorted(leaves):
            edges.append({"source":src,"source_packed_indices":list(coords),"source_bit":sbit,
                          **dest,"relation":"syntactic_influence_candidate"})
    return edges,fixed,sorted(ops)

def build_bitwise_dependencies(ast,index,captured,flat,*,enabled=True):
    items,edges=[],[]
    positions=0
    truncated=bool(enabled and flat["counts"]["truncated"])
    if enabled:
        resolver=SignalResolver(ast,index)
        declared=layouts(index)
        for ordinal,access,node,owner,constants,context_partial in captured:
            if flat["items"][ordinal]["coverage"]!="partial":
                continue
            scan_error=None
            try:
                if not has_operator(node.get("right")):
                    continue
            except Unsupported as exc:
                scan_error=str(exc)
            if len(items)>=MAX_ROWS:
                truncated=True
                break
            row={"flat_assignment_id":ordinal,"target":access["target"],
                 "source_location":access.get("source"),"coverage":"partial","edge_count":0,
                 "assignment_kind":access.get("assignment_kind","continuous"),
                 "procedure_kind":access.get("procedure_kind"),"nonblocking":access.get("nonblocking"),
                 "guards":access.get("guards",[]),"events":access.get("events",[]),
                 "timing_scope":access.get("timing_scope")}
            items.append(row)
            try:
                if scan_error:
                    raise Unsupported(scan_error)
                if context_partial:
                    raise Unsupported("unsupported_procedural_context")
                local,fixed,ops=expand(node,lambda e:resolver.resolve(owner,e),declared,constants)
                if any(e["target"]!=row["target"] for e in [*local,*fixed]):
                    raise Unsupported("assignment_target_identity_mismatch")
                if len(edges)+positions+len(local)+len(fixed)>MAX_EDGES:
                    raise Unsupported("edge_budget_exceeded")
            except Unsupported as exc:
                row["reason"]=str(exc)
                if str(exc) in ("edge_budget_exceeded","expression_traversal_budget",
                                "row_pair_budget","concat_operand_budget","lane_budget_exceeded","operator_scan_budget"):
                    truncated=True
                continue
            row.update(coverage="bitwise_influence_candidates",edge_count=len(local),
                       operators=ops,constant_target_positions=fixed)
            edges.extend({**e,"assignment_id":len(items)-1} for e in local)
            positions+=len(fixed)
    status=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"captured_flat_partial_bitwise_influence_candidates",
            "items":items,"edges":edges,"counts":{"captured":len(items),
                "supported":status["bitwise_influence_candidates"],"partial":status["partial"],
                "edges":len(edges),"truncated":truncated},
            "caveat":"Syntactic potential influence, not copies or exact functional dependence. "
                     "Masking, cancellation, guards, values and timing are not proven. "
                     "Constant positions mean no runtime RHS leaf, not an evaluated value."}
