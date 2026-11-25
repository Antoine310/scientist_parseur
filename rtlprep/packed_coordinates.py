"""Fixed multidimensional packed positions, without flattened bit numbers.

Only an explicitly selected final word, optional final bit/range, direct
copy or literal-only conversion chain. No procedural priority or value
proof. Legacy array coordinate functions remain unchanged.
"""
from .array_dependencies import (Unsupported, layout, decompose, coordinates,
    index_value, MAX_DIMENSIONS, MAX_WIDTH)
from .bit_widths import integral_shape, width
from .bit_width_literals import literal_width

def multidimensional(expr):
    for _ in range(MAX_DIMENSIONS+6):
        if not isinstance(expr,dict):
            return False
        typ=layout(expr.get("type"))
        if typ and not typ[2] and len(typ[1])>1:
            return True
        if expr.get("kind") in ("ElementSelect","RangeSelect"):
            expr=expr.get("value")
        elif expr.get("kind")=="Conversion":
            expr=expr.get("operand")
        else:
            return False
    return False

def selected(expr,resolve,declared,constants):
    base,chain=decompose(expr)
    typ=layout(base.get("type"))
    if typ is None or typ[2] or declared.get(resolve(base))!=typ:
        raise Unsupported("unproven_packed_layout")
    kind,dims,_=typ
    # Validate the elaborated result type at every selection, not
    # merely the total size of the last expression.
    for sel in chain:
        if not dims:
            raise Unsupported("extra_scalar_selection")
        if sel["kind"]=="ElementSelect":
            index_value(sel.get("selector"),constants,dims[0])
            dims=dims[1:]
        elif sel["kind"]=="RangeSelect" and len(dims)==1 and sel.get("selectionKind")=="Simple":
            left=index_value(sel.get("left"),constants,dims[0])
            right=index_value(sel.get("right"),constants,dims[0])
            if left!=right and (left>right)!=(dims[0][0]>dims[0][1]):
                raise Unsupported("range_direction_mismatch")
            dims=((left,right),)
        else:
            raise Unsupported("unsupported_packed_selection")
        if layout(sel.get("type"))!=(kind,dims,()):
            raise Unsupported("selection_type_mismatch")
    result=coordinates(expr,resolve,declared,constants)
    if result[1] or not 1<=len(result[3])<=MAX_WIDTH:
        raise Unsupported("unsupported_packed_coordinate_width")
    # integral_shape rejects ascending types; coordinate order is
    # proven independently here, including ascending final dimensions.
    end=layout(expr.get("type"))
    if end is None or end[2] or len(end[1])>1:
        raise Unsupported("unsupported_packed_result")
    n=abs(end[1][0][0]-end[1][0][1])+1 if end[1] else 1
    if n!=len(result[3]):
        raise Unsupported("packed_result_width_mismatch")
    return result,kind

def constant_chain(expr,depth=0):
    if depth>12 or not isinstance(expr,dict):
        raise Unsupported("constant_chain_limit")
    typ=integral_shape(expr.get("type"))
    if typ is None:
        raise Unsupported("unproven_literal_type")
    if expr.get("kind") in ("IntegerLiteral","UnbasedUnsizedIntegerLiteral"):
        if literal_width(expr)!=width(typ):
            raise Unsupported("unproven_literal_width")
    elif expr.get("kind")=="Conversion":
        # All leaves must be literal; value transformations are not
        # evaluated, so no claim of X/Z, sign or literal value.
        constant_chain(expr.get("operand"),depth+1)
    else:
        raise Unsupported("not_literal_conversion_chain")
    return width(typ)

def expand(node,resolve,declared,constants):
    if (node.get("kind")!="Assignment" or type(node.get("isNonBlocking")) is not bool
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not (multidimensional(lhs) or multidimensional(rhs)):
        raise Unsupported("not_multidimensional_packed")
    dst,kind=selected(lhs,resolve,declared,constants)
    if layout(node.get("type"))!=layout(lhs.get("type")):
        raise Unsupported("assignment_type_mismatch")
    if isinstance(rhs,dict) and rhs.get("kind") in ("IntegerLiteral","UnbasedUnsizedIntegerLiteral","Conversion"):
        try:
            n=constant_chain(rhs)
        except Unsupported:
            pass
        else:
            if n!=len(dst[3]):
                raise Unsupported("literal_assignment_width_mismatch")
            # These positions have no dynamic RHS source in this
            # assignment. No value field, unlike PR61's proven LUT.
            return [],[{"target":dst[0],"target_unpacked_indices":[],
                        "target_packed_indices":dst[2],"target_bit":b} for b in dst[3]]
    # Direct copies only; dynamic casts, operators, calls and muxes
    # are intentionally left for later semantic work.
    src,source_kind=selected(rhs,resolve,declared,constants)
    if kind!=source_kind or len(src[3])!=len(dst[3]):
        raise Unsupported("packed_copy_type_or_width_mismatch")
    return [{"source":src[0],"source_unpacked_indices":[],"source_packed_indices":src[2],
             "source_bit":s,"target":dst[0],"target_unpacked_indices":[],
             "target_packed_indices":dst[2],"target_bit":d}
            for s,d in zip(src[3],dst[3])], []
