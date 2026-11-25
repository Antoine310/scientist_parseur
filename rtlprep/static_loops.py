"""Bounded expansion of simple procedural bit-copy loops.

Assignment-local candidates only. No scheduling, final-write or influence
inference, and no changes to the historical dependency graph.
"""
from collections import Counter
from .constant_indices import evaluate, integer_value, normalize_positions
from .bitgraph import declared_bounds, selected_bounds
from .bitaccess import _graph_literal_position
from .symbols import SignalResolver
from .complex_constructs import location, LOOPS
from .function_dependencies import identity, link

MAX_ITERATIONS=64
MAX_ROWS=2000
MAX_EDGES=16384
MAX_SCAN=50000
MAX_DEPTH=24
INT_TYPES={"int","integer","int signed","integer signed"}

class Unsupported(ValueError):
    pass

def literal(node):
    if not isinstance(node,dict) or node.get("kind")!="IntegerLiteral":
        raise Unsupported("nonliteral_header")
    value=evaluate(node,{})
    if value is None:
        raise Unsupported("invalid_header_literal")
    return value

def for_values(loop,decl):
    """Single locally declared signed int, increment by one, < or <=."""
    if not isinstance(decl,dict) or decl.get("kind")!="Variable" or decl.get("type") not in INT_TYPES or decl.get("lifetime")!="Automatic":
        raise Unsupported("unproven_local_iterator")
    key=identity(decl)
    if key is None or loop.get("initializers")!=[]:
        raise Unsupported("unsupported_initializer")
    start=literal(decl.get("initializer"))
    stop=loop.get("stopExpr")
    steps=loop.get("steps")
    if not isinstance(stop,dict) or stop.get("kind")!="BinaryOp" or stop.get("op") not in ("LessThan","LessThanEqual"):
        raise Unsupported("unsupported_stop")
    def is_iterator(expr):
        return (isinstance(expr,dict) and expr.get("kind")=="NamedValue"
                and expr.get("type") in INT_TYPES and link(expr.get("symbol"))==key)
    if not is_iterator(stop.get("left")):
        raise Unsupported("stop_iterator_mismatch")
    end=literal(stop.get("right"))+(stop["op"]=="LessThanEqual")
    if not isinstance(steps,list) or len(steps)!=1:
        raise Unsupported("unsupported_step_count")
    step=steps[0]
    if (not isinstance(step,dict) or step.get("kind")!="UnaryOp"
            or step.get("op") not in ("Preincrement","Postincrement")
            or not is_iterator(step.get("operand"))):
        raise Unsupported("unsupported_step")
    count=max(0,end-start)
    if count>MAX_ITERATIONS:
        raise Unsupported("iteration_budget_exceeded")
    return key,list(range(start,end))

def single_assignment(body):
    for _ in range(MAX_DEPTH):
        if not isinstance(body,dict):
            break
        if body.get("kind")=="Block" and body.get("blockKind")=="Sequential" and not body.get("block"):
            body=body.get("body")
        elif body.get("kind")=="List" and isinstance(body.get("list"),list) and len(body["list"])==1:
            body=body["list"][0]
        elif body.get("kind")=="ExpressionStatement":
            expr=body.get("expr")
            if (isinstance(expr,dict) and expr.get("kind")=="Assignment"
                    and expr.get("isNonBlocking") is False and "op" not in expr
                    and "timingControl" not in expr):
                return expr
            break
        else:
            break
    raise Unsupported("not_single_blocking_assignment")

def bit_position(expr,constants,resolve,bounds):
    if not isinstance(expr,dict) or expr.get("kind")!="ElementSelect":
        raise Unsupported("not_direct_bit_select")
    base=expr.get("value")
    if not isinstance(base,dict) or base.get("kind")!="NamedValue":
        raise Unsupported("nested_or_non_signal_base")
    signal=resolve(base)
    if signal is None:
        raise Unsupported("unresolved_signal")
    selector=normalize_positions(expr,constants).get("selector")
    if not _graph_literal_position(selector):
        raise Unsupported("unresolved_selector")
    value=integer_value(selector["value"])
    if value is None:
        raise Unsupported("invalid_selector")
    try:
        selected_bounds({"kind":"bit","index":value},bounds.get(signal))
    except ValueError as exc:
        raise Unsupported(str(exc)) from exc
    return signal,value

def expand_loop(loop,decl,resolve,bounds):
    kind=loop.get("kind")
    assignment=single_assignment(loop.get("body"))
    if kind=="ForLoop":
        key,values=for_values(loop,decl)
    elif kind=="RepeatLoop":
        count=literal(loop.get("count"))
        if count>MAX_ITERATIONS:
            raise Unsupported("iteration_budget_exceeded")
        key=None
        values=list(range(count))
    else:
        raise Unsupported("unsupported_loop_kind")
    edges=[]
    for ordinal,value in enumerate(values):
        constants={key[0]:(key[1],value)} if key else {}
        target,tbit=bit_position(assignment.get("left"),constants,resolve,bounds)
        source,sbit=bit_position(assignment.get("right"),constants,resolve,bounds)
        if source==target:
            raise Unsupported("self_read_or_loop_carried_candidate")
        edges.append({"iteration":ordinal,"iterator_value":value if key else None,
                      "source":source,"source_bit":sbit,"target":target,"target_bit":tbit})
    return {"iteration_count":len(values),"iterator":key[1] if key else None,"edges":edges}

def local_blocks(members):
    """Collect statement-block declarations within one instance only."""
    result={}
    pending=list(members[:MAX_SCAN]) if isinstance(members,list) else []
    visited=0
    while pending:
        node=pending.pop()
        visited+=1
        if visited>MAX_SCAN:
            return {}
        if not isinstance(node,dict) or node.get("kind")!="StatementBlock":
            continue
        key=identity(node)
        if key is not None:
            result[key]=None if key in result else node
        children=node.get("members",[])
        if isinstance(children,list):
            if visited+len(pending)+len(children)>MAX_SCAN:
                return {}
            pending.extend(children)
    return result

def declared_loop(body,block):
    """Require exact declaration statement followed immediately by its loop."""
    if not isinstance(body,dict) or body.get("kind")!="List":
        return None
    parts=body.get("list")
    if not isinstance(parts,list) or len(parts)!=2:
        return None
    first,second=parts
    if (not isinstance(first,dict) or first.get("kind")!="VariableDeclaration"
            or not isinstance(second,dict) or second.get("kind")!="ForLoop"):
        return None
    key=link(first.get("symbol"))
    members=block.get("members",[]) if isinstance(block,dict) else []
    if key is None or not isinstance(members,list):
        return None
    matches=[m for m in members if identity(m)==key]
    if len(matches)!=1:
        return None
    return second,matches[0]

def build_static_loop_expansion(ast,*,index):
    resolver=SignalResolver(ast,index)
    bounds=declared_bounds(index)
    items=[]
    edges=[]
    visited=0
    truncated=False
    pending=[(ast.get("design",{}).get("members",[]),None,0)]
    def record(loop,owner,proc,decl=None):
        nonlocal truncated
        if len(items)>=MAX_ROWS:
            truncated=True
            return
        row={"instance":owner,"procedure_kind":proc,"ast_kind":loop["kind"],
             "source":location(loop),"coverage":"partial","iteration_count":None,"edge_count":0}
        items.append(row)
        try:
            if proc!="AlwaysComb":
                raise Unsupported("unsupported_procedure")
            data=expand_loop(loop,decl,lambda n:resolver.resolve(owner,n),bounds)
            local=data.pop("edges")
            if len(edges)+len(local)>MAX_EDGES:
                truncated=True
                raise Unsupported("edge_budget_exceeded")
            edges.extend({**e,"loop_id":len(items)-1} for e in local)
            row.update(data,coverage="static_iteration_position_candidates",edge_count=len(local))
        except Unsupported as exc:
            row["reason"]=str(exc)

    def statements(node,owner,proc,blocks,depth=0):
        nonlocal visited,truncated
        visited+=1
        if visited>MAX_SCAN or depth>MAX_DEPTH or len(items)>=MAX_ROWS:
            truncated=True
            return
        if not isinstance(node,dict):
            return
        kind=node.get("kind")
        if kind=="Block" and node.get("blockKind")=="Sequential":
            body=node.get("body")
            pair=declared_loop(body,blocks.get(link(node.get("block"))))
            if pair is not None:
                record(pair[0],owner,proc,pair[1])
            else:
                statements(body,owner,proc,blocks,depth+1)
        elif kind=="List":
            parts=node.get("list")
            if isinstance(parts,list):
                if len(parts)>MAX_SCAN-visited:
                    truncated=True
                    return
                for child in parts:
                    statements(child,owner,proc,blocks,depth+1)
        elif kind in LOOPS:
            record(node,owner,proc)
        # Conditional/timed/nested loops are not traversed or expanded.

    while pending:
        members,owner,depth=pending.pop()
        if not isinstance(members,list):
            continue
        if depth>MAX_DEPTH or visited+len(members)>MAX_SCAN:
            truncated=True
            continue
        visited+=len(members)
        blocks=local_blocks(members)
        for node in members:
            if not isinstance(node,dict):
                continue
            kind=node.get("kind")
            if kind=="Instance" and isinstance(node.get("body"),dict) and isinstance(node.get("name"),str):
                child=f"{owner}.{node['name']}" if owner else node["name"]
                pending.append((node["body"].get("members",[]),child,depth+1))
            elif kind in ("GenerateBlock","GenerateBlockArray","Scope") and node.get("isUninstantiated") is not True:
                pending.append((node.get("members",[]),owner,depth+1))
            elif kind=="ProceduralBlock" and owner is not None:
                statements(node.get("body"),owner,node.get("procedureKind"),blocks)
        if visited>=MAX_SCAN or len(items)>=MAX_ROWS:
            truncated=True
            break
    counts=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"direct_procedural_static_bit_copy_loops",
            "items":items,"edges":edges,"counts":{"captured":len(items),
                "supported":counts["static_iteration_position_candidates"],"partial":counts["partial"],
                "edges":len(edges),"truncated":truncated},
            "caveat":"Assignment-local syntactic positions per iteration only; no final write, "
                     "global writer, execution scheduling, functional influence or design coverage. "
                     "Nested/conditional/timed loops are outside this traversal."}
