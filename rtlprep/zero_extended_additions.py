"""PR97: zero-extended additions with lexically proven fixed selections."""
from .addition_candidates import audit_additions, result_shape, coordinate_set
from .array_dependencies import Unsupported, decompose
from .packed_coordinates import selected
from .constant_indices import evaluate
from .bit_width_literals import literal_width


def endpoint(expr,resolve,raw,declared,constants):
    base,chain=decompose(expr)
    sig=resolve(base)
    if sig is None or raw.get(sig)!=base.get("type"):
        raise Unsupported("unproven_exact_signal_identity_or_type")
    proofs=[]
    for level,sel in enumerate(chain):
        if sel["kind"]=="RangeSelect" and sel.get("selectionKind")!="Simple":
            raise Unsupported("unsupported_packed_selection")
        for key in ("selector",) if sel["kind"]=="ElementSelect" else ("left","right"):
            original=sel.get(key)
            v=evaluate(original,constants,allow_power=False)
            if v is None:
                raise Unsupported("unproven_lexical_selector")
            proofs.append({"selection_level_from_base":level,"field":key,"index":v,
                           "original_expression":original,
                           "evidence":"bounded_lexical_constant_evaluation"})
    loc,kind=selected(expr,resolve,declared,constants)
    state,n=result_shape(expr)
    if kind!=state or loc[0]!=sig or len(loc[3])!=n or loc[1]:
        raise Unsupported("endpoint_layout_disagreement")
    return {"signal":sig,"outer_packed_indices":loc[2],"bits_lsb_first":loc[3],
            "declared_type":base["type"],"expression_type":expr["type"],
            "selector_proofs":proofs}


def operand(expr,state,n,resolve,raw,declared,constants):
    if not isinstance(expr,dict) or expr.get("kind")!="Concatenation":
        raise Unsupported("not_single_zero_extended_operand")
    if result_shape(expr)!=(state,n):
        raise Unsupported("addition_width_or_state_mismatch")
    parts=expr.get("operands")
    if not isinstance(parts,list) or len(parts)!=2:
        raise Unsupported("not_single_zero_extended_operand")
    zero,leaf=parts
    if (not isinstance(zero,dict) or zero.get("kind")!="IntegerLiteral"
            or literal_width(zero)!=1 or evaluate(zero,{})!=0):
        raise Unsupported("unproven_single_zero_prefix")
    if result_shape(leaf)!=(state,n-1):
        raise Unsupported("zero_extended_leaf_width_or_state_mismatch")
    ep=endpoint(leaf,resolve,raw,declared,constants)
    ep["extension"]={"kind":"explicit_msb_zero","width":1,"literal":zero}
    return ep


def expand(node,resolve,raw,declared,constants):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(rhs,dict) or rhs.get("kind")!="BinaryOp" or rhs.get("op")!="Add":
        raise Unsupported("not_direct_addition")
    if not isinstance(lhs,dict) or node.get("type")!=lhs.get("type"):
        raise Unsupported("assignment_type_mismatch")
    state,n=result_shape(lhs)
    if n<2 or result_shape(rhs)!=(state,n):
        raise Unsupported("addition_width_or_state_mismatch")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    src=[operand(rhs.get(k),state,n,resolve,raw,declared,constants) for k in ("left","right")]
    if coordinate_set(src[0]) & coordinate_set(src[1]):
        raise Unsupported("overlapping_operand_coordinates")
    prefixes=[min(i+1,n-1) for i in range(n)]
    return {"operator":"Add","width":n,"state":state,"target":dst,"operands":src,
            "relation":"zero_extended_addition_potential_influence_candidate",
            "representation":"lsb_prefix_per_operand","prefix_lengths":prefixes,
            "potential_pairs":2*sum(prefixes),"value_equivalence":"not_proven",
            "guard_feasibility":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_zero_extended_additions(ast,index,graph):
    result=audit_additions(ast,index,graph,_expand=expand)
    result["scope"]="residual_flat_zero_extended_addition_roots_only"
    return result
