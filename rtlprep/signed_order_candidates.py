"""Strict signed comparison of two data slices with one shared sign control.

Recognizes only $signed({msb & control, data}) > same shape.
Coordinates refer to original runtime sources, not replicated sign bits.
"""
from .addition_candidates import _audit_arithmetic, coordinate_set, result_shape
from .array_dependencies import Unsupported
from .zero_extended_additions import endpoint


def operand(expr,resolve,raw,declared,constants):
    if not isinstance(expr,dict) or expr.get("kind")!="Call" or expr.get("subroutine")!="$signed":
        raise Unsupported("not_exact_signed_call")
    args=expr.get("arguments")
    if not isinstance(args,list) or len(args)!=1:
        raise Unsupported("signed_call_arity")
    concat=args[0]
    if not isinstance(concat,dict) or concat.get("kind")!="Concatenation":
        raise Unsupported("not_sign_concat")
    parts=concat.get("operands")
    if not isinstance(parts,list) or len(parts)!=2:
        raise Unsupported("sign_concat_arity")
    sign,data=parts
    state,n=result_shape(data)
    if state!="logic" or not 2<=n<=32 or concat.get("type")!=f"logic[{n}:0]" or expr.get("type")!=f"logic signed[{n}:0]":
        raise Unsupported("unproven_signed_width_or_state")
    if (not isinstance(sign,dict) or sign.get("kind")!="BinaryOp"
            or sign.get("op")!="BinaryAnd" or result_shape(sign)!=("logic",1)):
        raise Unsupported("not_single_bit_sign_and")
    a,b=sign.get("left"),sign.get("right")
    if any(result_shape(x)!=("logic",1) for x in (a,b)):
        raise Unsupported("sign_and_operand_shape")
    data_ep=endpoint(data,resolve,raw,declared,constants)
    msb,control=[endpoint(x,resolve,raw,declared,constants) for x in (a,b)]
    high=(data_ep["signal"],tuple(data_ep["outer_packed_indices"]),data_ep["bits_lsb_first"][-1])
    if coordinate_set(msb)!={high}:
        raise Unsupported("sign_not_data_msb")
    if coordinate_set(control)&coordinate_set(data_ep):
        raise Unsupported("control_aliases_data")
    return data_ep,control,n,msb


def expand(node,resolve,raw,declared,constants):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if (not isinstance(rhs,dict) or rhs.get("kind")!="BinaryOp" or rhs.get("op")!="GreaterThan"):
        raise Unsupported("not_direct_greater_than")
    if not isinstance(lhs,dict) or node.get("type")!=lhs.get("type") or any(result_shape(e)!=("logic",1) for e in (lhs,rhs)):
        raise Unsupported("comparison_result_not_matching_scalar")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    a,ca,na,ma=operand(rhs.get("left"),resolve,raw,declared,constants)
    b,cb,nb,mb=operand(rhs.get("right"),resolve,raw,declared,constants)
    if na!=nb:
        raise Unsupported("comparison_data_width_mismatch")
    if coordinate_set(ca)!=coordinate_set(cb):
        raise Unsupported("sign_control_not_shared")
    sets=[coordinate_set(e) for e in (a,b,ca)]
    if any(sets[i]&sets[j] for i in range(3) for j in range(i+1,3)):
        raise Unsupported("overlapping_runtime_coordinates")
    if coordinate_set(dst)&set.union(*sets):
        raise Unsupported("target_aliases_runtime_source")
    return {"operator":"GreaterThan","operand_width":na,"state":"logic","target":dst,
            "operands":[a,b,ca],"operand_roles":["left_data","right_data","shared_sign_control"],
            "sign_msb_evidence":[ma,mb],"shared_control_occurrences":2,
            "relation":"controlled_signed_order_potential_influence_candidate",
            "representation":"unique_runtime_coordinates_to_scalar",
            "potential_pairs":2*na+1,"model_domain":"defined_binary_inputs_only",
            "value_equivalence":"not_proven","guard_feasibility":"not_proven","timing":"not_proven"}


def audit_signed_order(ast,index,graph):
    report=_audit_arithmetic(ast,index,graph,operator="GreaterThan",
                             coverage="signed_order_candidates",expand_candidate=expand)
    report["scope"]="residual_flat_controlled_signed_greater_than_roots_only"
    return report
