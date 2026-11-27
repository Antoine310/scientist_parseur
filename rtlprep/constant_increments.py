"""Assignment-local increment candidates with exact fixed coordinates.

Binary defined-input semantics only. An aligned address has no runtime
source for its two low result bits. Neither the compact representation nor
the model proof establishes global influence or state-transition priority.
"""
from .addition_candidates import audit_additions, result_shape
from .array_dependencies import Unsupported
from .zero_extended_additions import endpoint
from .bit_width_literals import literal_width
from .constant_indices import evaluate


def literal_constant(expr, state, n):
    if result_shape(expr)!=(state,n):
        raise Unsupported("increment_constant_type_mismatch")
    leaf=expr
    if expr.get("kind")=="Conversion":
        leaf=expr.get("operand")
    if not isinstance(leaf,dict) or leaf.get("kind")!="IntegerLiteral" or literal_width(leaf) is None:
        raise Unsupported("increment_constant_not_literal")
    value=evaluate(expr,{})
    if value not in (1,4):
        raise Unsupported("unproven_increment_constant")
    return value


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
    left,right=rhs.get("left"),rhs.get("right")
    if any(result_shape(e)!=(state,n) for e in (rhs,left,right)):
        raise Unsupported("increment_width_or_state_mismatch")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    value=literal_constant(right,state,n)
    if value==1:
        source=endpoint(left,resolve,raw,declared,constants)
        shift=0
    else:
        if n!=32 or left.get("kind")!="Concatenation":
            raise Unsupported("not_aligned_address_increment")
        parts=left.get("operands")
        if not isinstance(parts,list) or len(parts)!=2:
            raise Unsupported("not_aligned_address_increment")
        leaf,zero=parts
        if (not isinstance(zero,dict) or zero.get("kind")!="IntegerLiteral"
                or literal_width(zero)!=2 or evaluate(zero,{})!=0):
            raise Unsupported("unproven_alignment_zero_suffix")
        if result_shape(leaf)!=(state,n-2):
            raise Unsupported("alignment_leaf_width_or_state_mismatch")
        source=endpoint(leaf,resolve,raw,declared,constants)
        shift=2
    prefixes=[max(0,i-shift+1) for i in range(n)]
    return {"operator":"Add","width":n,"state":state,"target":dst,"operands":[source],
            "constant_addend":value,"constant_expression":right,
            "low_zero_input_bits":shift,"constant_result_positions":[
                {"bit":bit,"value":0} for bit in dst["bits_lsb_first"][:shift]],
            "relation":"constant_increment_potential_influence_candidate",
            "representation":"lsb_prefix_single_operand","prefix_lengths":prefixes,
            "potential_pairs":sum(prefixes),"value_equivalence":"not_proven",
            "guard_feasibility":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_increments(ast,index,graph):
    result=audit_additions(ast,index,graph,_expand=expand)
    result["scope"]="residual_flat_constant_increment_roots_only"
    return result
