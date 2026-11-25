"""Additional width handling for already-captured assignment candidates."""
import re
from .bit_widths import integral_shape, width, resize_parts

def literal_width(node):
    """Read elaborated integral width and a serialized literal, not source text.

    This establishes constant positions, never the actual bit values.
    """
    if node.get("kind") not in ("IntegerLiteral","UnbasedUnsizedIntegerLiteral"):
        return None
    shape=integral_shape(node.get("type"))
    if shape is None:
        return None
    n=width(shape)
    raw=node.get("value")
    if type(raw) is int:
        return n if raw.bit_length()<=n else None
    if not isinstance(raw,str) or len(raw)>4096:
        return None
    value=raw.replace("_","")
    if re.fullmatch(r"-?[0-9]+",value):
        # Decimal serialization may be unsized; use the elaborated type.
        if len(value)>310:
            return None
        return n if int(value).bit_length()<=n else None
    if re.fullmatch(r"'[01xXzZ]",value):
        return n if node["kind"]=="UnbasedUnsizedIntegerLiteral" else None
    match=re.fullmatch(r"([0-9]+)'[sS]?([bBoOdDhH])(-?[0-9a-fA-FxXzZ?]+)",value)
    if not match or len(match[1])>4 or int(match[1])!=n:
        return None
    base=match[2].lower()
    digits=match[3]
    alphabet={"b":"[01xXzZ?]+","o":"[0-7xXzZ?]+","d":"(?:-?[0-9]+|[xXzZ?])","h":"[0-9a-fA-FxXzZ?]+"}[base]
    return n if re.fullmatch(alphabet,digits) else None

def resize_constant_state(parts,source,dest):
    """Allow different state domains only if no runtime source is involved."""
    if source is None or dest is None:
        raise ValueError("conversion_width_unproven_or_changed")
    if source[3]!=dest[3]:
        if any(p[0] is not None for p in parts):
            raise ValueError("conversion_state_change_unmodeled")
        # Unknown-to-zero changes values but cannot introduce a runtime
        # dependency. Neither this helper nor the bit graph encodes values.
        normalized=(*source[:3],dest[3])
        result,mode=resize_parts(parts,normalized,dest)
        return result,"constant_state_"+mode
    return resize_parts(parts,source,dest)
