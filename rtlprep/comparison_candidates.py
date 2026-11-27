"""Assignment-local equality candidates, defined binary inputs only.

The result is not a bit copy, RTL equivalence, or global influence.
"""
from .addition_candidates import _audit_arithmetic, result_shape, coordinate_set
from .array_dependencies import Unsupported
from .bit_width_literals import literal_width
from .constant_indices import evaluate, integer_value
from .zero_extended_additions import endpoint

OPERATORS=("Equality","Inequality","LessThan","LessThanEqual","GreaterThan","GreaterThanEqual",
           "CaseEquality","CaseInequality","WildcardEquality","WildcardInequality")


def constant_operand(expr,state,n,constants):
    """One literal, or low slice of a proven lexical int unsigned parameter.

    A same-width conversion of a defined constant can change state domain.
    Never infer a value from the serialized folded tag alone.
    """
    if result_shape(expr)!=(state,n):
        raise Unsupported("comparison_operand_shape_mismatch")
    leaf=expr.get("operand") if expr.get("kind")=="Conversion" else expr
    _,width=result_shape(leaf)
    if width!=n:
        raise Unsupported("comparison_constant_width_changed")
    if leaf.get("kind")=="IntegerLiteral":
        if literal_width(leaf)!=n:
            raise Unsupported("unproven_comparison_literal_width")
        value=evaluate(leaf,{})
    elif leaf.get("kind")=="RangeSelect":
        base=leaf.get("value")
        if (leaf.get("selectionKind")!="Simple" or not isinstance(base,dict)
                or base.get("kind")!="NamedValue" or base.get("type")!="int unsigned"
                or leaf.get("type")!=f"bit[{n-1}:0]" or n>32):
            raise Unsupported("unsupported_comparison_parameter_slice")
        high=evaluate(leaf.get("left"),constants)
        low=evaluate(leaf.get("right"),constants)
        v=evaluate(base,constants)
        if high!=n-1 or low!=0 or v is None:
            raise Unsupported("unproven_comparison_parameter_slice")
        value=v&((1<<n)-1)
    else:
        raise Unsupported("unsupported_comparison_constant")
    if value is None or not 0<=value<1<<n:
        raise Unsupported("unproven_comparison_constant_value")
    for node in (leaf,expr):
        if "constant" in node and integer_value(node["constant"])!=value:
            raise Unsupported("comparison_constant_tag_disagreement")
    return value


def expand(node,resolve,raw,declared,constants):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(rhs,dict) or rhs.get("kind")!="BinaryOp":
        raise Unsupported("not_direct_comparison")
    op=rhs.get("op")
    if op not in ("Equality","Inequality"):
        raise Unsupported("comparison_order_or_four_state_outside_scope")
    if not isinstance(lhs,dict) or node.get("type")!=lhs.get("type"):
        raise Unsupported("assignment_type_mismatch")
    state,width=result_shape(lhs)
    if width!=1 or result_shape(rhs)!=(state,1):
        raise Unsupported("comparison_result_not_matching_scalar")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    left,right=rhs.get("left"),rhs.get("right")
    source_state,n=result_shape(left)
    if source_state!=state or result_shape(right)!=(state,n):
        raise Unsupported("comparison_operand_shape_mismatch")
    src=[]
    sides=[]
    fixed=[]
    for side,operand in enumerate((left,right)):
        # Exact runtime endpoint first; a tag on a signal is not a constant.
        if operand.get("kind") in ("NamedValue","RangeSelect","ElementSelect"):
            try:
                ep=endpoint(operand,resolve,raw,declared,constants)
            except Unsupported:
                if operand.get("kind")!="RangeSelect":
                    raise
            else:
                src.append(ep)
                sides.append(side)
                continue
        fixed.append({"side":side,"value":constant_operand(operand,state,n,constants),
                      "expression":operand})
    if not src or len(fixed)>1:
        raise Unsupported("comparison_requires_runtime_operand")
    if len(src)==2 and coordinate_set(src[0])&coordinate_set(src[1]):
        raise Unsupported("overlapping_operand_coordinates")
    return {"operator":op,"operand_width":n,"state":state,"target":dst,
            "operands":src,"operand_sides":sides,"constant_operands":fixed,
            "relation":"equality_potential_influence_candidate",
            "representation":"all_operand_positions_to_scalar",
            "potential_pairs":sum(len(e["bits_lsb_first"]) for e in src),
            "value_equivalence":"not_proven","guard_feasibility":"not_proven",
            "timing":"not_proven","model_domain":"defined_binary_inputs_only"}


def audit_comparisons(ast,index,graph):
    report=_audit_arithmetic(ast,index,graph,operator=OPERATORS,
                             coverage="comparison_candidates",expand_candidate=expand)
    report["scope"]="residual_flat_comparison_roots_only"
    return report
