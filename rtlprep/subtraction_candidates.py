"""Assignment-local modular subtraction and bounded shift-mask candidates.

Only defined binary inputs. Distinguish the arithmetic model from RTL
equivalence and from global dependence. No change to historical graphs.
"""
from .addition_candidates import _audit_arithmetic, result_shape, coordinate_set
from .array_dependencies import Unsupported
from .constant_increments import literal_constant
from .zero_extended_additions import endpoint


def mask_offsets(i):
    # For bit i, (1 << k)-1 is 1 exactly when k > i (0 <= k <= 31).
    # Toggling a bit below the trailing zeros of i+1 cannot cross that
    # threshold. Bit 31 is always zero in this defined-input model.
    if i==31:
        return []
    threshold=i+1
    first=(threshold & -threshold).bit_length()-1
    return list(range(first,5))


def expand(node,resolve,raw,declared,constants):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(rhs,dict) or rhs.get("kind")!="BinaryOp" or rhs.get("op")!="Subtract":
        raise Unsupported("not_direct_subtraction")
    if not isinstance(lhs,dict) or node.get("type")!=lhs.get("type"):
        raise Unsupported("assignment_type_mismatch")
    state,n=result_shape(lhs)
    left,right=rhs.get("left"),rhs.get("right")
    if any(result_shape(e)!=(state,n) for e in (rhs,left,right)):
        raise Unsupported("subtraction_width_or_state_mismatch")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    common={"operator":"Subtract","width":n,"state":state,"target":dst,
            "value_equivalence":"not_proven","guard_feasibility":"not_proven",
            "timing":"not_proven","model_domain":"defined_binary_inputs_only"}
    if left.get("kind")=="BinaryOp" and left.get("op")=="LogicalShiftLeft":
        if n!=32 or result_shape(left.get("right"))!=(state,5):
            raise Unsupported("unproven_shift_mask_width_or_state")
        if literal_constant(left.get("left"),state,n)!=1 or literal_constant(right,state,n)!=1:
            raise Unsupported("not_one_shift_minus_one")
        src=endpoint(left["right"],resolve,raw,declared,constants)
        offsets=[mask_offsets(i) for i in range(32)]
        return {**common,"operands":[src],"relation":"shift_mask_potential_influence_candidate",
                "representation":"source_offsets_per_result_position",
                "source_offsets_by_result":offsets,"potential_pairs":sum(map(len,offsets)),
                "constant_result_positions":[{"bit":dst["bits_lsb_first"][31],"value":0}],
                "shift_base":left["left"],"subtrahend":right}
    src=[endpoint(e,resolve,raw,declared,constants) for e in (left,right)]
    if coordinate_set(src[0]) & coordinate_set(src[1]):
        raise Unsupported("overlapping_operand_coordinates")
    return {**common,"operands":src,"relation":"modular_subtraction_potential_influence_candidate",
            "representation":"lsb_prefix_per_operand","prefix_lengths":list(range(1,n+1)),
            "potential_pairs":n*(n+1),"constant_result_positions":[]}


def audit_subtractions(ast,index,graph):
    result=_audit_arithmetic(ast,index,graph,operator="Subtract",
                             coverage="subtraction_candidates",expand_candidate=expand)
    result["scope"]="residual_flat_subtraction_roots_only"
    return result
