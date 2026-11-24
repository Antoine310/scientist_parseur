"""Conservative normalization of elaborated constant selector expressions.

Only local Parameter declarations in the active lexical scope are accepted.
Arithmetic is bounded, typed and nonnegative; no wrap, sign changes of
negative values, unknown bits or runtime constant tags are inferred.
"""
from __future__ import annotations

import re

MAX_VALUE=1024
MAX_DEPTH=12
MAX_NODES=256
MAX_SCOPE_CONSTANTS=256


def integer_value(raw):
    if type(raw) is int:
        return raw if 0<=raw<=MAX_VALUE else None
    if not isinstance(raw,str) or len(raw)>64:
        return None
    raw=raw.strip().replace("_","")
    if raw.isdecimal():
        v=int(raw)
        return v if v<=MAX_VALUE else None
    m=re.fullmatch(r"(\d+)'([sS]?)([bBoOdDhH])([0-9a-fA-F]+)",raw)
    if not m:
        return None
    width=int(m[1])
    if not 1<=width<=1024:
        return None
    try:
        v=int(m[4],{"b":2,"o":8,"d":10,"h":16}[m[3].lower()])
    except ValueError:
        return None
    return v if v<=MAX_VALUE and v < (1 << (width-bool(m[2]))) else None


def fits(value,type_string):
    if value is None or not isinstance(type_string,str) or len(type_string)>96:
        return False
    if type_string in ("int","integer","int signed","integer signed"):
        return value < (1<<31)
    if type_string in ("int unsigned","integer unsigned"):
        return value < (1<<32)
    if type_string in ("logic","bit","reg"):
        return value<=1
    m=re.fullmatch(r"(?:logic|bit|reg)(?: (signed|unsigned))?\s*\[(\d+):(\d+)\]",type_string)
    if not m:
        return False
    width=abs(int(m[2])-int(m[3]))+1
    return 1<=width<=1024 and value < (1 << (width-(m[1]=="signed")))


def scope_constants(members,parent=None):
    """Collect only direct lexical localparams, rejecting duplicate addresses.

    Caller resets the map at instance boundaries and never enters inactive
    generate blocks. No global name lookup, even when names are unique.
    """
    result=dict(parent or {})
    if not isinstance(members,list):
        return result
    for node in members:
        if not isinstance(node,dict):
            continue
        addr=node.get("addr")
        if type(addr) is not int and not isinstance(addr,str):
            continue
        addr=str(addr)
        if not addr.isdecimal():
            continue
        if addr in result:
            result[addr]=None
            continue
        if node.get("kind")!="Parameter" or node.get("isLocal") is not True:
            continue
        name=node.get("name")
        v=integer_value(node.get("value"))
        if isinstance(name,str) and name and fits(v,node.get("type")):
            result[addr]=(name,v)
            if len(result)>MAX_SCOPE_CONSTANTS:
                return {}
    return result


def evaluate(node,constants,depth=0,budget=None):
    if budget is None:
        budget=[MAX_NODES]
    budget[0]-=1
    if budget[0]<0 or depth>MAX_DEPTH or not isinstance(node,dict):
        return None
    kind=node.get("kind")
    if kind=="IntegerLiteral":
        value=integer_value(node.get("value"))
    elif kind=="NamedValue":
        raw=node.get("symbol")
        parts=raw.split(maxsplit=1) if isinstance(raw,str) and len(raw)<=192 else []
        if len(parts)!=2:
            return None
        entry=constants.get(parts[0])
        if entry is None or entry[0]!=parts[1]:
            return None
        value=entry[1]
    elif kind in ("Conversion","SignedConversion"):
        value=evaluate(node.get("operand"),constants,depth+1,budget)
    elif kind=="BinaryOp" and node.get("op") in ("Add","Subtract","Multiply"):
        left=evaluate(node.get("left"),constants,depth+1,budget)
        right=evaluate(node.get("right"),constants,depth+1,budget)
        if left is None or right is None:
            return None
        op=node["op"]
        value=left+right if op=="Add" else left-right if op=="Subtract" else left*right
    else:
        return None
    if value is None or not 0<=value<=MAX_VALUE or not fits(value,node.get("type")):
        return None
    if "constant" in node and integer_value(node["constant"])!=value:
        return None
    return value


def normalize_positions(node,constants,depth=0,budget=None):
    """Return a copy of supported expression paths with proven selectors.

    The original AST is untouched. Unsupported expressions are returned
    unchanged for the existing strict bit-graph gate to reject.
    """
    if budget is None:
        budget=[MAX_NODES]
    budget[0]-=1
    if budget[0]<0 or depth>MAX_DEPTH or not isinstance(node,dict):
        return node
    kind=node.get("kind")
    if kind in ("ElementSelect","RangeSelect"):
        if kind=="RangeSelect" and node.get("selectionKind")!="Simple":
            return node
        if not isinstance(node.get("value"),dict) or node["value"].get("kind")!="NamedValue":
            return node
        fields=("selector",) if kind=="ElementSelect" else ("left","right")
        result=dict(node)
        for field in fields:
            selector=node.get(field)
            if isinstance(selector,dict) and selector.get("kind")=="IntegerLiteral":
                continue
            v=evaluate(selector,constants,budget=budget)
            if v is None:
                return node
            result[field]={"kind":"IntegerLiteral","value":str(v)}
        return result
    if kind=="Concatenation":
        parts=node.get("operands")
        if not isinstance(parts,list) or len(parts)>32:
            return node
        return {**node,"operands":[normalize_positions(p,constants,depth+1,budget) for p in parts]}
    field="concat" if kind=="Replication" else "operand" if kind in ("Conversion","SignedConversion","UnaryOp") else None
    if field is not None:
        return {**node,field:normalize_positions(node.get(field),constants,depth+1,budget)}
    return node
