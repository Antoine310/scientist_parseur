"""Bounded additive return-reference candidates for simple local functions."""
from collections import Counter
from .symbols import SignalResolver
from .complex_constructs import location

MAX_ARGS=32
MAX_NODES=256
MAX_DEPTH=16
MAX_ROWS=2000
MAX_SCAN=50000
BINARY={"Add","Subtract","Multiply","BinaryAnd","BinaryOr","BinaryXor",
        "BinaryXnor","LogicalAnd","LogicalOr","Equality","Inequality",
        "LessThan","LessThanEqual","GreaterThan","GreaterThanEqual"}
UNARY={"Plus","Minus","BitwiseNot","LogicalNot","ReductionAnd","ReductionOr",
       "ReductionXor","ReductionNand","ReductionNor","ReductionXnor"}

class Unsupported(ValueError):
    pass

def identity(node):
    if not isinstance(node,dict):
        return None
    addr=node.get("addr")
    name=node.get("name")
    if type(addr) not in (str,int) or not str(addr).isdecimal() or not isinstance(name,str) or not name:
        return None
    return str(addr),name

def link(raw):
    parts=raw.split(maxsplit=1) if isinstance(raw,str) and len(raw)<=192 else []
    return tuple(parts) if len(parts)==2 and parts[0].isdecimal() and parts[1] else None

def expression_refs(node,resolve,depth=0,budget=None):
    if budget is None:
        budget=[MAX_NODES]
    budget[0]-=1
    if budget[0]<0 or depth>MAX_DEPTH or not isinstance(node,dict):
        raise Unsupported("expression_budget_or_shape")
    kind=node.get("kind")
    if kind=="NamedValue":
        ref=resolve(node)
        if ref is None:
            raise Unsupported("unresolved_or_nonformal_reference")
        return {ref}
    if kind=="IntegerLiteral":
        if type(node.get("value")) not in (str,int):
            raise Unsupported("malformed_literal")
        return set()
    if kind=="BinaryOp" and node.get("op") in BINARY:
        children=[node.get("left"),node.get("right")]
    elif (kind=="UnaryOp" and node.get("op") in UNARY) or kind in ("Conversion","SignedConversion"):
        children=[node.get("operand")]
    elif kind=="Concatenation":
        children=node.get("operands")
    else:
        raise Unsupported("unsupported_expression_"+str(kind)[:48])
    if not isinstance(children,list) or not 1<=len(children)<=MAX_ARGS:
        raise Unsupported("expression_children")
    refs=set()
    for child in children:
        refs.update(expression_refs(child,resolve,depth+1,budget))
    return refs

def single_return(body):
    for _ in range(MAX_DEPTH):
        if not isinstance(body,dict):
            break
        kind=body.get("kind")
        if kind=="Return":
            return body.get("expr")
        if kind=="Block" and body.get("blockKind")=="Sequential" and not body.get("block"):
            body=body.get("body")
        elif kind=="List" and isinstance(body.get("list"),list) and len(body["list"])==1:
            body=body["list"][0]
        else:
            break
    raise Unsupported("not_single_explicit_return")

def summarize_function(node):
    if (node.get("subroutineKind")!="Function"
            or node.get("defaultLifetime")!="Automatic" or node.get("flags")):
        raise Unsupported("not_plain_automatic_function")
    args=node.get("arguments")
    if not isinstance(args,list) or len(args)>MAX_ARGS:
        raise Unsupported("malformed_formals")
    formal={}
    for i,arg in enumerate(args):
        key=identity(arg)
        if (key is None or key in formal or arg.get("kind")!="FormalArgument"
                or arg.get("direction")!="In" or "defaultValue" in arg):
            raise Unsupported("unsupported_formal")
        formal[key]=i
    members=node.get("members",[])
    if not isinstance(members,list) or len(members)>MAX_ARGS+1:
        raise Unsupported("unsupported_function_members")
    for member in members:
        if not isinstance(member,dict):
            raise Unsupported("malformed_function_member")
        if member.get("kind")=="FormalArgument" and identity(member) in formal:
            continue
        if (member.get("kind")=="Variable" and member.get("name")==node.get("name")
                and "initializer" not in member and "init" not in member):
            continue
        raise Unsupported("unsupported_function_member")
    used=expression_refs(single_return(node.get("body")),lambda n:formal.get(link(n.get("symbol"))))
    return len(args),sorted(used)

def resolve_call(call,functions,resolve):
    key=link(call.get("subroutine"))
    if key is None or functions.get(key) is None:
        raise Unsupported("unresolved_local_function_identity")
    definition=functions[key]
    arity,used=summarize_function(definition)
    args=call.get("arguments",[])
    if "args" in call or not isinstance(args,list) or len(args)!=arity:
        raise Unsupported("argument_count_or_shape")
    # Validate even unused actual arguments: no hidden calls or side effects.
    budget=[MAX_NODES]
    actual=[expression_refs(a,resolve,budget=budget) for a in args]
    refs=set().union(*(actual[i] for i in used))
    return {"callee":key[1],"definition_source":location(definition),
            "used_argument_positions":used,
            "unused_argument_positions":[i for i in range(arity) if i not in used],
            "return_signal_references":sorted(refs),
            "argument_signal_references":[sorted(r) for r in actual]}

def build_function_dependencies(ast,*,index):
    resolver=SignalResolver(ast,index)
    items=[]
    pending=[(ast.get("design",{}).get("members",[]),None,{},0)]
    visited=0
    truncated=False
    while pending:
        members,owner,functions,depth=pending.pop()
        if not isinstance(members,list):
            continue
        if depth>MAX_DEPTH or visited+len(members)>MAX_SCAN:
            truncated=True
            continue
        visited+=len(members)
        for node in members:
            if not isinstance(node,dict):
                continue
            kind=node.get("kind")
            if kind=="Instance":
                name=node.get("name")
                body=node.get("body")
                if not isinstance(name,str) or not isinstance(body,dict):
                    continue
                path=f"{owner}.{name}" if owner else name
                children=body.get("members",[])
                local={}
                if isinstance(children,list):
                    for child in children[:MAX_SCAN]:
                        if isinstance(child,dict) and child.get("kind")=="Subroutine":
                            key=identity(child)
                            if key is not None:
                                local[key]=None if key in local else child
                pending.append((children,path,local,depth+1))
            elif kind in ("GenerateBlock","GenerateBlockArray","Scope"):
                if node.get("isUninstantiated") is not True:
                    pending.append((node.get("members"),owner,functions,depth+1))
            elif kind=="ContinuousAssign" and owner is not None:
                assignment=node.get("assignment")
                if not isinstance(assignment,dict) or assignment.get("kind")!="Assignment":
                    continue
                rhs=assignment.get("right")
                # Allow the usual outer conversion around a call.
                for _ in range(MAX_DEPTH):
                    if isinstance(rhs,dict) and rhs.get("kind") in ("Conversion","SignedConversion"):
                        rhs=rhs.get("operand")
                    else:
                        break
                if not isinstance(rhs,dict) or rhs.get("kind")!="Call":
                    continue
                if len(items)>=MAX_ROWS:
                    truncated=True
                    break
                target=resolver.resolve(owner,assignment.get("left"))
                row={"instance":owner,"target":target,"source":location(rhs),
                     "callee":None,"coverage":"partial"}
                try:
                    if target is None:
                        raise Unsupported("unsupported_assignment_target")
                    row.update(resolve_call(rhs,functions,lambda n:resolver.resolve(owner,n)))
                    row["coverage"]="return_reference_candidates"
                except Unsupported as exc:
                    row["reason"]=str(exc)
                items.append(row)
        if len(items)>=MAX_ROWS:
            truncated=True
            break
    counts=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"direct_continuous_calls_to_local_single_return_functions",
            "items":items,"counts":{"captured":len(items),"supported":counts["return_reference_candidates"],
            "partial":counts["partial"],"truncated":truncated},
            "caveat":"Syntactic return references only; no functional influence, bit mapping, "
                     "global driver completeness or proof. Other call contexts are not inventoried here."}
