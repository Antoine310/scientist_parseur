"""Bounded per-analysis row policy; no ambient global mutation."""
MAX_CONFIGURABLE_ROWS = 8192

def effective_row_limit(requested, default):
    value = default if requested is None else requested
    if type(value) is not int or not 1 <= value <= MAX_CONFIGURABLE_ROWS:
        raise ValueError("analyzer row limit must be an integer in 1..8192")
    return value
