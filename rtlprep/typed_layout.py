"""Recover explicit package typedef/enum layouts without name-only resolution.

Only direct package declarations, exact address + qualified type tokens,
and unsigned logic/bit layouts. Private assignment normalization; the
original AST and index are unchanged. Structs/unions remain unsupported.
"""
from collections import Counter, defaultdict
import re
from .array_dependencies import Unsupported, layout, layouts
from .constant_indices import scope_constants, evaluate
from .dynamic_dependencies import expand as expand_dynamic, plan, positions
from .symbols import SignalResolver

MAX_ROWS=2000
MAX_EDGES=32768
MAX_DEPTH=16
MAX_NODES=512
MAX_TYPES=256
MAX_PACKAGE_MEMBERS=4096
MAX_PROOFS=64
IDENT=re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")
TOKEN=re.compile(r"([0-9]+) ([A-Za-z_$][A-Za-z0-9_$]*::[A-Za-z_$][A-Za-z0-9_$]*)\Z")
REASONS=frozenset(("unproven_declared_layout","unproven_packed_layout"))
BUDGET_REASONS=frozenset(("type_scan_budget","type_proof_budget","edge_budget_exceeded",
    "choice_budget_exceeded","row_pair_budget","lane_budget_exceeded",
    "expression_traversal_budget","concat_operand_budget"))

def identity(n):
    addr=n.get("addr")
    if type(addr) is int or isinstance(addr,str):
        s=str(addr)
        if s.isdecimal() and len(s)<=32:
            return s
    return None

def packages(ast):
    """Only direct package members in compilation units or root."""
    root=ast.get("design",{}).get("members",[])
    result=[]
    for n in root:
        if not isinstance(n,dict):
            continue
        if n.get("kind")=="Package":
            result.append(n)
        elif n.get("kind")=="CompilationUnit":
            result.extend(x for x in n.get("members",[]) if isinstance(x,dict) and x.get("kind")=="Package")
    return result

class Types:
    def __init__(self,ast):
        self.types={}
        self.constants={}
        self.truncated=False
        candidates=defaultdict(list)
        consts=defaultdict(list)
        pkgs=packages(ast)
        names=Counter(p.get("name") for p in pkgs if isinstance(p.get("name"),str))
        count=0
        for p in pkgs:
            name=p.get("name")
            if not isinstance(name,str) or not IDENT.fullmatch(name) or names[name]!=1:
                continue
            members=p.get("members",[])
            count+=len(members)
            if count>MAX_PACKAGE_MEMBERS:
                self.truncated=True
                return
            for n in members:
                if not isinstance(n,dict):
                    continue
                addr=identity(n)
                if addr is None:
                    continue
                nm=n.get("name")
                candidates[addr].append((name,n))
                if n.get("kind")=="Parameter" and isinstance(nm,str) and IDENT.fullmatch(nm):
                    entry=scope_constants([n]).get(addr)
                    if entry is not None:
                        consts[addr].append((entry,n.get("type"),name))
        for addr,entries in candidates.items():
            if len(entries)!=1:
                continue
            pkg,n=entries[0]
            nm=n.get("name")
            if not isinstance(nm,str) or not IDENT.fullmatch(nm):
                continue
            if n.get("kind") in ("TypeAlias","EnumType"):
                if len(self.types)>=MAX_TYPES:
                    self.truncated=True
                    return
                self.types[addr+" "+pkg+"::"+nm]=n
            elif len(consts[addr])==1:
                self.constants[addr]=consts[addr][0]

    def resolve(self,raw):
        if not isinstance(raw,str):
            return None
        seen=set()
        current=raw
        for _ in range(MAX_DEPTH):
            typ=layout(current)
            if typ is not None:
                return current if seen else None
            if current in seen or not TOKEN.fullmatch(current):
                return None
            seen.add(current)
            n=self.types.get(current)
            if n is None:
                return None
            if n["kind"]=="EnumType":
                base=n.get("baseType")
                t=layout(base)
                # enum must have a single integral base, not an aggregate.
                return base if t is not None and not t[2] and len(t[1])<=1 else None
            current=n.get("target")
            if not isinstance(current,str):
                return None
        return None

def normalize(node,types,resolve,raw_declared,constants):
    proofs=[]
    declared={}
    budget=[MAX_NODES]
    def proof(p):
        if len(proofs)>=MAX_PROOFS:
            raise Unsupported("type_proof_budget")
        proofs.append(p)
    def walk(n,path,depth):
        budget[0]-=1
        if budget[0]<0 or depth>MAX_DEPTH:
            raise Unsupported("type_scan_budget")
        if not isinstance(n,dict):
            raise Unsupported("malformed_expression")
        kind=n.get("kind")
        result=dict(n)
        raw=n.get("type")
        if kind=="NamedValue":
            signal=resolve(n)
            if signal is None:
                raise Unsupported("unproven_signal_identity")
            if raw_declared.get(signal)!=raw:
                raise Unsupported("declaration_type_disagreement")
            canonical=types.resolve(raw)
            if canonical is not None:
                result["type"]=canonical
                proof({"ast_path":path,"kind":"package_type","signal":signal,
                       "declared_type":raw.split(" ",1)[1],"canonical_type":canonical})
            t=layout(result.get("type"))
            if t is None:
                raise Unsupported("unproven_package_layout")
            if signal in declared and declared[signal]!=t:
                raise Unsupported("declaration_type_disagreement")
            declared[signal]=t
            return result
        if kind in ("IntegerLiteral","UnbasedUnsizedIntegerLiteral"):
            return result
        if kind=="Assignment":
            fields=("left","right")
        elif kind in ("ElementSelect","RangeSelect"):
            fields=("value",)
        else:
            raise Unsupported("unsupported_typed_expression")
        for field in fields:
            result[field]=walk(n.get(field),path+[field],depth+1)
        selectors=("selector",) if kind=="ElementSelect" else (
            ("left","right") if kind=="RangeSelect" and n.get("selectionKind")=="Simple" else ())
        for field in selectors:
            expr=n.get(field)
            value=evaluate(expr,constants)
            if value is not None:
                continue
            if isinstance(expr,dict) and expr.get("kind")=="NamedValue":
                token=expr.get("symbol")
                parts=token.split(maxsplit=1) if isinstance(token,str) else []
                entry=types.constants.get(parts[0]) if len(parts)==2 else None
                if entry is not None and parts[0] not in constants and resolve(expr) is None:
                    pair,typ,pkg=entry
                    if pair[0]==parts[1] and typ==expr.get("type"):
                        value=evaluate(expr,{parts[0]:pair})
                        if value is not None:
                            result[field]={"kind":"IntegerLiteral","type":typ,"value":str(value)}
                            proof({"ast_path":path+[field],"kind":"package_constant",
                                   "parameter":pkg+"::"+pair[0],"type":typ,"index":value})
                            continue
            result[field]=walk(expr,path+[field],depth+1)
        return result
    rewritten=walk(node,[],0)
    if not any(p["kind"]=="package_type" for p in proofs):
        raise Unsupported("no_proven_package_type")
    return rewritten,declared,proofs

def expand(node,types,resolve,raw_declared,constants):
    if (node.get("kind")!="Assignment" or type(node.get("isNonBlocking")) is not bool
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_assignment")
    n,declared,proofs=normalize(node,types,resolve,raw_declared,constants)
    lhs,rhs=n["left"],n["right"]
    dst=plan(lhs,resolve,declared,constants)
    src=plan(rhs,resolve,declared,constants)
    if dst["dynamic"] or src["dynamic"]:
        edges,domain,alternatives=expand_dynamic(n,resolve,declared,constants)
        return edges,{"mode":"dynamic","selector":domain,"alternatives":alternatives},proofs
    if layout(n.get("type"))!=layout(lhs.get("type")) or src["state"]!=dst["state"] or len(src["bits"])!=len(dst["bits"]):
        raise Unsupported("assignment_width_or_state_mismatch")
    edges=[{**s,**d,"relation":"typed_fixed_position_candidate"} for s,d in
           zip(positions(src,None,"source"),positions(dst,None,"target"))]
    return edges,{"mode":"fixed"},proofs

def raw_layouts(index):
    candidates=defaultdict(set)
    for i in index["instances"]:
        for p in i["ports"]:
            candidates[i["path"]+"."+p["name"]].add(p.get("type"))
    for s in index["signals"]:
        candidates[s.get("path") or s["instance_path"]+"."+s["name"]].add(s.get("type"))
    return {k:next(iter(v)) for k,v in candidates.items() if len(v)==1}

def build_typed_layout(ast,index,captured,flat,dynamic,*,enabled=True):
    items,edges=[],[]
    truncated=bool(enabled and (flat["counts"]["truncated"] or dynamic["counts"]["truncated"]))
    if enabled:
        types=Types(ast)
        truncated|=types.truncated
        eligible={r["flat_assignment_id"] for r in dynamic["items"]
                  if r["coverage"]=="partial" and r.get("reason") in REASONS}
        resolver=SignalResolver(ast,index)
        raw=raw_layouts(index)
        for ordinal,access,node,owner,constants,context_partial in captured:
            if ordinal not in eligible:
                continue
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
                if context_partial:
                    raise Unsupported("unsupported_procedural_context")
                if types.truncated:
                    raise Unsupported("package_inventory_budget")
                local,detail,proofs=expand(node,lambda e:resolver.resolve(owner,e),raw,constants)
                if any(e["target"]!=row["target"] for e in local):
                    raise Unsupported("assignment_target_identity_mismatch")
                if len(edges)+len(local)>MAX_EDGES:
                    raise Unsupported("edge_budget_exceeded")
            except Unsupported as exc:
                row["reason"]=str(exc)
                if str(exc) in BUDGET_REASONS:
                    truncated=True
                continue
            row.update(coverage="typed_layout_candidates",edge_count=len(local),
                       type_proofs=proofs,**detail)
            edges.extend({**e,"assignment_id":len(items)-1} for e in local)
    status=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"pr74_layout_residuals_package_types",
            "items":items,"edges":edges,"counts":{"captured":len(items),
            "supported":status["typed_layout_candidates"],"partial":status["partial"],
            "edges":len(edges),"truncated":truncated},
            "caveat":"Exact package type tokens and declaration-relative candidates. "
                     "No enum reachability, value, temporal, or functional influence proof; "
                     "struct/union and unsupported type layouts remain partial."}
