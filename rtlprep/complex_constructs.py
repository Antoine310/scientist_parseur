"""Bounded inventory of complex elaborated AST constructs, not execution."""
from __future__ import annotations

import re
from collections import Counter
from .symbols import SignalResolver
from .bitaccess import _number

MAX_NODES = 50000
MAX_ROWS = 2000
MAX_DEPTH = 48
MAX_ARGS = 32
MAX_REFS = 128
MAX_REPEAT = 64

LOOPS = {"ForLoop", "RepeatLoop", "ForeachLoop", "WhileLoop", "DoWhileLoop", "ForeverLoop"}
METADATA = {"type", "definition", "internalSymbol", "symbol", "addr", "subroutine"}


def location(node):
    file = node.get("source_file_start") or node.get("source_file")
    line = node.get("source_line_start") or node.get("source_line")
    return {"file":file,"line":line if type(line) is int and line>0 else None} if isinstance(file,str) and file else None


def literal_index(node):
    # Do not reinterpret conversions, signed negatives, X/Z or runtime
    # constant tags as literal indices.
    if not isinstance(node,dict) or node.get("kind")!="IntegerLiteral":
        return None
    value=node.get("value")
    if isinstance(value,str) and re.search(r"'[sS]",value):
        # Signed bit patterns can be negative. Accept only decimal syntax.
        if not re.fullmatch(r"\d+'[sS][dD][0-9_]+",value):
            return None
        width,digits=re.split(r"'[sS][dD]",value)
        if not 1<=int(width)<=1024 or int(digits.replace("_",""))>=2**(int(width)-1):
            return None
    return _number(value)


def reference_summary(node, resolve):
    """References in expression syntax only; unresolved locals stay unknown."""
    pending=[(node,0)]
    found=set()
    unknown=0
    visited=0
    while pending:
        obj,depth=pending.pop()
        visited+=1
        if visited>MAX_REFS or depth>16:
            return {"signal_references":sorted(found),"unresolved_references":unknown,
                    "complete":False,"truncated":True}
        if isinstance(obj,list):
            pending.extend((x,depth+1) for x in reversed(obj[:MAX_REFS]))
            if len(obj)>MAX_REFS:
                return {"signal_references":sorted(found),"unresolved_references":unknown,
                        "complete":False,"truncated":True}
        elif isinstance(obj,dict):
            if obj.get("kind")=="NamedValue":
                signal=resolve(obj)
                if signal is None:
                    unknown+=1
                else:
                    found.add(signal)
                continue
            for key,child in obj.items():
                if key not in METADATA and isinstance(child,(dict,list)):
                    pending.append((child,depth+1))
    return {"signal_references":sorted(found),"unresolved_references":unknown,
            "complete":unknown==0,"truncated":False}


def call_record(node,resolve):
    raw=node.get("subroutine")
    # Keep only name, not the ephemeral AST declaration address.
    name=None
    if isinstance(raw,str) and len(raw)<=192:
        parts=raw.split(maxsplit=1)
        candidate=parts[1] if len(parts)==2 and parts[0].isdecimal() else raw
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*",candidate):
            name=candidate
    args=node.get("arguments",[])
    if not isinstance(args,list) or len(args)>MAX_ARGS:
        return {"kind":"call","callee":name,"coverage":"partial","reason":"malformed_or_bounded_arguments","arguments":[]}
    return {"kind":"call","callee":name,"coverage":"partial",
            "reason":"callee_semantics_not_resolved",
            "arguments":[{"position":i,**reference_summary(a,resolve)} for i,a in enumerate(args)]}


def selection_record(node,resolve):
    fields=("selector",) if node["kind"]=="ElementSelect" else ("left","right")
    selectors=[]
    for field in fields:
        expr=node.get(field)
        value=literal_index(expr)
        refs=reference_summary(expr,resolve)
        selectors.append({"field":field,"literal_index":value,
            "classification":"literal_index" if value is not None else
                "runtime_reference_candidate" if refs["signal_references"] else "unknown_or_nonliteral",
            **refs})
    return {"kind":"selection","ast_kind":node["kind"],
            "selection_kind":node.get("selectionKind") if node.get("selectionKind") in ("Simple","IndexedUp","IndexedDown") else None,
            "base_references":reference_summary(node.get("value"),resolve),
            "selectors":selectors,"coverage":"syntax_observed",
            "layout":"not_resolved","bit_mapping":None}


def loop_record(node,resolve):
    kind=node["kind"]
    result={"kind":"loop","ast_kind":kind,"coverage":"partial",
            "reason":"loop_execution_not_resolved","literal_repeat_count":None,
            "unrolled":False}
    if kind=="RepeatLoop":
        count=literal_index(node.get("count"))
        result["header_references"]=reference_summary(node.get("count"),resolve)
        if count is not None and count<=MAX_REPEAT:
            result["literal_repeat_count"]=count
            result["reason"]="literal_repeat_header_only"
        elif count is not None:
            result["reason"]="repeat_count_exceeds_bound"
    elif kind=="ForLoop":
        result["header_references"]=reference_summary(
            [node.get("initializers"),node.get("stopExpr"),node.get("steps")],resolve)
        stop=node.get("stopExpr")
        if isinstance(stop,dict) and stop.get("kind")=="BinaryOp" and stop.get("op") in ("LessThan","LessThanEqual","GreaterThan","GreaterThanEqual"):
            result["comparison_operator"]=stop["op"]
            result["comparison_literal"]=literal_index(stop.get("right"))
        result["reason"]="for_header_observed_no_trip_count"
    else:
        result["header_references"]=reference_summary(node.get("cond") or node.get("arrayRef"),resolve)
    return result


def build_complex_construct_index(ast,*,index):
    resolver=SignalResolver(ast,index)
    items=[]
    pending=[(ast.get("design",{}).get("members",[]),None,0,None)]
    visited=0
    truncated=False
    while pending:
        obj,owner,depth,context=pending.pop()
        visited+=1
        if visited>MAX_NODES or len(items)>=MAX_ROWS:
            truncated=True
            break
        if depth>MAX_DEPTH:
            truncated=True
            continue
        if isinstance(obj,list):
            # Limit traversal queue growth as well as visited work.
            available=max(0,MAX_NODES-visited-len(pending))
            if len(obj)>available:
                truncated=True
            pending.extend((x,owner,depth+1,context) for x in reversed(obj[:available]))
            continue
        if not isinstance(obj,dict):
            continue
        kind=obj.get("kind")
        if kind=="Instance":
            name=obj.get("name")
            body=obj.get("body")
            if isinstance(name,str) and isinstance(body,dict):
                path=f"{owner}.{name}" if owner else name
                pending.append((body.get("members",[]),path,depth+1,None))
            continue
        if kind in ("GenerateBlock","GenerateBlockArray","Scope"):
            if obj.get("isUninstantiated") is not True:
                pending.append((obj.get("members",[]),owner,depth+1,context))
            continue
        if owner is None:
            continue
        if kind=="ProceduralBlock":
            pending.append((obj.get("body"),owner,depth+1,"procedural"))
            continue
        if kind=="ContinuousAssign":
            pending.append((obj.get("assignment"),owner,depth+1,"continuous"))
            continue
        # Do not mistake declaration initializers or uncalled function
        # bodies for runtime call sites.
        if context is None:
            continue
        resolve=lambda node: resolver.resolve(owner,node)
        row=None
        if kind=="Call":
            row=call_record(obj,resolve)
        elif kind in ("ElementSelect","RangeSelect"):
            row=selection_record(obj,resolve)
        elif kind in LOOPS:
            row=loop_record(obj,resolve)
        if row is not None:
            items.append({"instance":owner,"context":context,"source":location(obj),**row})
        for key,child in reversed(list(obj.items())):
            if key not in METADATA and isinstance(child,(dict,list)):
                pending.append((child,owner,depth+1,context))
    counts=Counter(r["kind"] for r in items)
    return {"schema_version":1,"scope":"procedural_and_continuous_ast_constructs",
            "items":items,"counts":{"captured":len(items),"calls":counts["call"],
                "selections":counts["selection"],"loops":counts["loop"],"truncated":truncated},
            "caveat":"Observed argument and selector references only; no function return influence, "
                     "array layout, loop unrolling, execution count or functional proof."}
