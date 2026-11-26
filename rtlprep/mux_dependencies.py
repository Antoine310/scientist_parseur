"""Bounded assignment-local mux data/control candidates with branch provenance.

Branch paths describe syntax, not feasible or exclusive Boolean guards:
SystemVerilog ?: can merge both arms for an unknown condition.
"""
from collections import Counter
from .array_dependencies import layout, layouts, Unsupported
from .packed_coordinates import selected
from .bitwise_dependencies import expression, shape
from .symbols import SignalResolver

MAX_ROWS=2000
MAX_EDGES=16384
MAX_WIDTH=1024
MAX_DEPTH=8
MAX_NODES=256
MAX_BRANCHES=32
MAX_ROW_PAIRS=8192
COMPARISONS=frozenset(("Equality","Inequality","CaseEquality","CaseInequality",
                       "LessThan","LessThanEqual","GreaterThan","GreaterThanEqual"))
LOGICAL=frozenset(("LogicalAnd","LogicalOr"))
BUDGET_REASONS=frozenset(("mux_depth_budget","mux_node_budget","mux_branch_budget",
    "mux_row_pair_budget","edge_budget_exceeded","expression_traversal_budget",
    "row_pair_budget","concat_operand_budget","lane_budget_exceeded"))

def tick(budget,depth):
    budget[0]-=1
    if budget[0]<0:
        raise Unsupported("mux_node_budget")
    if depth>MAX_DEPTH:
        raise Unsupported("mux_depth_budget")

def root_mux(expr):
    # Only explicit root mux (possibly through conversions).
    for _ in range(MAX_DEPTH+1):
        if not isinstance(expr,dict):
            return False
        if expr.get("kind")=="ConditionalOp":
            return True
        if expr.get("kind")!="Conversion":
            return False
        expr=expr.get("operand")
    return False

def condition(expr,resolve,declared,constants,budget,depth=0):
    """Return condition candidate leaves, never evaluate its truth."""
    tick(budget,depth)
    n,_=shape(expr)
    kind,op=expr.get("kind"),expr.get("op")
    if kind=="BinaryOp" and op in COMPARISONS:
        a,b=expr.get("left"),expr.get("right")
        if n!=1 or shape(a)[0]!=shape(b)[0]:
            raise Unsupported("comparison_width_mismatch")
        aa=expression(a,resolve,declared,constants,set(),budget)
        bb=expression(b,resolve,declared,constants,set(),budget)
        leaves=set().union(*aa,*bb)
    elif kind=="BinaryOp" and op in LOGICAL:
        if n!=1:
            raise Unsupported("logical_result_not_scalar")
        leaves=condition(expr.get("left"),resolve,declared,constants,budget,depth+1)|condition(
            expr.get("right"),resolve,declared,constants,budget,depth+1)
    elif kind=="UnaryOp" and op=="LogicalNot":
        if n!=1:
            raise Unsupported("logical_result_not_scalar")
        leaves=condition(expr.get("operand"),resolve,declared,constants,budget,depth+1)
    else:
        lanes=expression(expr,resolve,declared,constants,set(),budget)
        leaves=set().union(*lanes)
    if len(leaves)>MAX_ROW_PAIRS:
        raise Unsupported("mux_row_pair_budget")
    return leaves

def expand(node,resolve,declared,constants):
    if (node.get("kind")!="Assignment" or type(node.get("isNonBlocking")) is not bool
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    dst,_=selected(lhs,resolve,declared,constants)
    n,state=shape(lhs)
    if layout(node.get("type"))!=layout(lhs.get("type")) or len(dst[3])!=n or shape(rhs)!=(n,state):
        raise Unsupported("assignment_type_or_width_mismatch")
    budget=[MAX_NODES]
    decisions=[]
    branches=[]
    edges=[]
    pair_count=0
    def destination(bit):
        return {"target":dst[0],"target_packed_indices":dst[2],"target_bit":bit}
    def add(src,bit,relation,identity):
        nonlocal pair_count
        pair_count+=1
        if pair_count>MAX_ROW_PAIRS:
            raise Unsupported("mux_row_pair_budget")
        signal,coords,sbit=src
        edges.append({"source":signal,"source_packed_indices":list(coords),"source_bit":sbit,
                      **destination(bit),"relation":relation,**identity})
    def visit(expr,path,ast_path,depth):
        nonlocal pair_count
        tick(budget,depth)
        m,st=shape(expr)
        if m!=n:
            raise Unsupported("mux_branch_width_mismatch")
        kind=expr.get("kind")
        if kind=="Conversion" and root_mux(expr):
            if shape(expr.get("operand"))!=(n,st) or st!=state:
                raise Unsupported("mux_conversion_width_or_state_change")
            visit(expr["operand"],path,ast_path+["operand"],depth+1)
            return
        if kind=="ConditionalOp":
            if st!=state:
                raise Unsupported("mux_state_mismatch")
            conds=expr.get("conditions")
            if (not isinstance(conds,list) or len(conds)!=1 or not isinstance(conds[0],dict)
                    or set(conds[0])!={"expr"} or not isinstance(conds[0]["expr"],dict)):
                raise Unsupported("unsupported_mux_condition_form")
            cond=conds[0]["expr"]
            leaves=condition(cond,resolve,declared,constants,budget,depth+1)
            ident=len(decisions)
            decisions.append({"decision_id":ident,"path":path,"rhs_ast_path":ast_path,
                              "condition_kind":cond.get("kind"),"condition_operator":cond.get("op"),
                              "condition_type":cond.get("type"),"condition_width":shape(cond)[0],
                              "control_source_count":len(leaves)})
            for bit in dst[3]:
                for src in sorted(leaves):
                    add(src,bit,"mux_control_candidate",{"decision_id":ident})
            visit(expr.get("left"),path+[{"decision_id":ident,"arm":"true"}],
                  ast_path+["left"],depth+1)
            visit(expr.get("right"),path+[{"decision_id":ident,"arm":"false"}],
                  ast_path+["right"],depth+1)
            return
        if len(branches)>=MAX_BRANCHES:
            raise Unsupported("mux_branch_budget")
        ops=set()
        lanes=expression(expr,resolve,declared,constants,ops,budget)
        if st!=state and any(lanes):
            raise Unsupported("mux_branch_state_mismatch")
        if len(lanes)!=n:
            raise Unsupported("mux_branch_width_mismatch")
        ident=len(branches)
        fixed=[]
        for bit,leaves in zip(dst[3],lanes):
            if not leaves:
                pair_count+=1
                if pair_count>MAX_ROW_PAIRS:
                    raise Unsupported("mux_row_pair_budget")
                fixed.append(destination(bit))
            for src in sorted(leaves):
                add(src,bit,"mux_data_candidate",{"branch_id":ident})
        branches.append({"branch_id":ident,"path":path,"rhs_ast_path":ast_path,
                         "operators":sorted(ops),"constant_target_positions":fixed})
    visit(rhs,[],[],0)
    if not decisions:
        raise Unsupported("no_root_mux")
    return edges,decisions,branches

def build_mux_dependencies(ast,index,captured,flat,*,enabled=True):
    items,edges=[],[]
    fixed_count=0
    truncated=bool(enabled and flat["counts"]["truncated"])
    if enabled:
        resolver=SignalResolver(ast,index)
        declared=layouts(index)
        for ordinal,access,node,owner,constants,context_partial in captured:
            if flat["items"][ordinal]["coverage"]!="partial" or not root_mux(node.get("right")):
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
                local,decisions,branches=expand(node,lambda e:resolver.resolve(owner,e),declared,constants)
                fixed=[p for b in branches for p in b["constant_target_positions"]]
                if any(e["target"]!=row["target"] for e in [*local,*fixed]):
                    raise Unsupported("assignment_target_identity_mismatch")
                if len(edges)+fixed_count+len(local)+len(fixed)>MAX_EDGES:
                    raise Unsupported("edge_budget_exceeded")
            except Unsupported as exc:
                row["reason"]=str(exc)
                if str(exc) in BUDGET_REASONS:
                    truncated=True
                continue
            row.update(coverage="mux_influence_candidates",edge_count=len(local),
                       decisions=decisions,branches=branches)
            edges.extend({**e,"assignment_id":len(items)-1} for e in local)
            fixed_count+=len(fixed)
    status=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"captured_flat_partial_root_mux_candidates",
            "items":items,"edges":edges,"counts":{"captured":len(items),
                "supported":status["mux_influence_candidates"],"partial":status["partial"],
                "edges":len(edges),"truncated":truncated},
            "caveat":"Branch-local data and decision-local control candidates, not copies or proven "
                     "influence. Unknown conditions may merge both arms. No feasibility, "
                     "priority, timing or value proof. Branch constants are not global constants."}
