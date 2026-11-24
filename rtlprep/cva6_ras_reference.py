"""Independent two-entry RAS behavioral model, top first."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Entry:
    valid: bool = False
    address: int = 0

def transition(stack, *, reset=False, flush=False, push=False, pop=False, address=0):
    if len(stack) != 2 or type(address) is not int or not 0 <= address < 2**32:
        raise ValueError("invalid RAS state or address")
    if reset or flush:
        return (Entry(), Entry())
    if push and pop:
        return (Entry(True,address), stack[1])
    if push:
        return (Entry(True,address), stack[0])
    if pop:
        return (stack[1], Entry())
    return tuple(stack)
