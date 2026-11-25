"""Conservative positional resizing of explicitly typed integral expressions.

Slang v12.1 serializes Conversion.operand but not ConversionKind.
Widening with different input/output signedness is therefore ambiguous:
propagated conversions use destination signedness, others operand signedness.
Do not infer a sign-extension policy in that case.
"""
import re

MAX_WIDTH=1024
MAX_SEGMENTS=32

def integral_shape(raw):
    """(hi, lo, signed, four_state), only explicit descending layouts."""
    if not isinstance(raw,str) or len(raw)>96:
        return None
    atom=re.fullmatch(r"(byte|shortint|int|integer|longint|time)(?: (signed|unsigned))?",raw)
    if atom:
        kind,sign=atom.groups()
        width={"byte":8,"shortint":16,"int":32,"integer":32,"longint":64,"time":64}[kind]
        return width-1,0,(kind!="time" if sign is None else sign=="signed"),kind in ("integer","time")
    vector=re.fullmatch(r"(logic|bit|reg)(?: (signed|unsigned))?(?:\[(\d+):(\d+)\])?",raw)
    if not vector:
        return None
    kind,sign,hi,lo=vector.groups()
    hi,lo=(int(hi),int(lo)) if hi is not None else (0,0)
    if not 0<=lo<=hi<=65535 or hi-lo+1>MAX_WIDTH:
        return None
    return hi,lo,sign=="signed",kind!="bit"

def width(shape):
    return shape[0]-shape[1]+1

def conversion_mode(source,dest):
    if source is None or dest is None:
        raise ValueError("conversion_width_unproven_or_changed")
    if source[3]!=dest[3]:
        raise ValueError("conversion_state_change_unmodeled")
    a,b=width(source),width(dest)
    if a==b:
        return "same_width"
    if b<a:
        return "truncate_msb"
    if source[2]!=dest[2]:
        raise ValueError("conversion_extension_signedness_ambiguous")
    return "sign_extend" if source[2] else "zero_extend"

def view(part,offset,span,repeat=False):
    """Slice relative to the proven segment LSB; repeat exactly one bit.

    Keep original width/selection for a second validation against declared
    bounds at the graph stage. Constants denote no runtime source, not value.
    """
    source,selection,n=part
    if type(offset) is not int or type(span) is not int or not 1<=span<=MAX_WIDTH or not 0<=offset<n:
        raise ValueError("conversion_slice_invalid")
    if not repeat and offset+span>n:
        raise ValueError("conversion_slice_invalid")
    if not repeat and offset==0 and span==n:
        return source,dict(selection),span
    transform=selection.get("_value_transform")
    if source is None:
        if selection.get("kind") not in ("literal","constant_reference") or selection.get("width")!=n:
            raise ValueError("conversion_constant_unproven")
        result={"kind":"constant_reference","width":span}
    else:
        result={"kind":"conversion_view",
                "base":{k:v for k,v in selection.items() if k!="_value_transform"},
                "base_width":n,"offset":offset,"repeat":repeat,"width":span}
    if transform is not None:
        result["_value_transform"]=transform
    return source,result,span

def resize_parts(parts,source,dest):
    mode=conversion_mode(source,dest)
    a,b=width(source),width(dest)
    if not parts or sum(p[2] for p in parts)!=a:
        raise ValueError("conversion_width_mismatch")
    if mode=="same_width":
        result=parts
    elif mode=="zero_extend":
        result=[(None,{"kind":"literal","width":b-a},b-a),*parts]
    elif mode=="sign_extend":
        result=[view(parts[0],parts[0][2]-1,b-a,True),*parts]
    else:
        remaining=b
        low=[]
        for part in reversed(parts):
            if not remaining:
                break
            n=min(remaining,part[2])
            low.append(view(part,0,n))
            remaining-=n
        result=list(reversed(low))
    if len(result)>MAX_SEGMENTS or sum(p[2] for p in result)!=b:
        raise ValueError("conversion_segment_budget")
    return result,mode
