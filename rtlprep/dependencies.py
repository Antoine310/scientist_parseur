"""Graphe de dépendances RTL conservateur, dérivé de l'AST élaboré slang.

Portée MVP : affectations simples, expressions de base, conditions if/ternaires,
événements always_ff et liaisons de ports In/Out. Aucune interprétation de
netlists, de fonctions, de tâches ou de generate complexes. Les cas non
reconnus sont signalés, jamais inférés à partir de texte source.
"""
from __future__ import annotations

from collections import deque
import re
from typing import Any

from .index import build_index
from .expressions import build_expression_index
from .flow import build_register_flow
from .bitaccess import build_bit_access_index, _constant as _static_integer
from .coverage import build_coverage_summary
from .sequential import build_sequential_candidates
from .intercycle import build_intercycle_dependencies
from .complex_constructs import build_complex_construct_index
from .bitgraph import build_bit_dependency_graph
from .function_dependencies import build_function_dependencies
from .static_loops import build_static_loop_expansion
from .array_dependencies import build_array_dependencies
from .bitwise_dependencies import build_bitwise_dependencies
from .mux_dependencies import build_mux_dependencies
from .dynamic_dependencies import build_dynamic_dependencies
from .selector_recovery import build_selector_recovery
from .typed_layout import build_typed_layout
from .analysis_budgets import DEFAULT_BUDGET, AnalysisBudget, inspect_ast, build_analysis_limits
from .symbols import SignalResolver, member_name

GRAPH_SCHEMA_VERSION = 1
LITERALS = frozenset({"IntegerLiteral", "RealLiteral", "StringLiteral",
                      "Null", "EmptyArgument", "UnbasedUnsizedIntegerLiteral"})
BINARY = frozenset({"BinaryOp"})
UNARY = frozenset({"UnaryOp", "Conversion", "SignedConversion"})


def _location(node: dict[str, Any]) -> dict[str, Any] | None:
    path = node.get("source_file_start") or node.get("source_file")
    line = node.get("source_line_start") or node.get("source_line")
    if not isinstance(path, str) or not path:
        return None
    return {"file": path, "line": line if isinstance(line, int) and line > 0 else None}


def _symbol_name(node: dict[str, Any]) -> str | None:
    """slang 12.1 écrit 'adresse nom' : ignorer l'adresse instable."""
    value = node.get("symbol")
    if not isinstance(value, str):
        return None
    parts = value.split(maxsplit=1)
    return parts[1] if len(parts) == 2 and parts[1] else None


def _integral_cast_type(raw: Any) -> tuple[int, bool, bool] | None:
    """Explicit integral width, signedness, four-state flag; no alias inference."""
    if not isinstance(raw, str) or len(raw) > 128:
        return None
    fixed = re.fullmatch(r"(byte|shortint|int|integer|longint)(?: (signed|unsigned))?", raw)
    if fixed:
        base, sign = fixed.groups()
        return ({"byte": 8, "shortint": 16, "int": 32, "integer": 32, "longint": 64}[base],
                sign != "unsigned", base == "integer")
    vector = re.fullmatch(r"(logic|bit|reg)(?: (signed|unsigned))?(?:\[(-?\d{1,5}):(-?\d{1,5})\])?", raw)
    if vector:
        base, sign, left, right = vector.groups()
        width = abs(int(left)-int(right))+1 if left is not None else 1
        if width <= 1024:
            return width, sign == "signed", base != "bit"
    return None


def _sign_cast_operand(expr: dict[str, Any]) -> dict[str, Any] | None:
    """Slang emits builtin names directly, but user calls as address/name links."""
    if expr.get("kind") != "Call" or expr.get("subroutine") not in ("$signed", "$unsigned"):
        return None
    if any(k in expr for k in ("thisClass", "iterExpr", "iterVar", "inlineConstraints", "randConstraintRestrictions")):
        return None
    args = expr.get("arguments")
    if not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], dict):
        return None
    operand = args[0]
    a = _integral_cast_type(operand.get("type"))
    b = _integral_cast_type(expr.get("type"))
    if a is None or b is None or a[0] != b[0] or a[2] != b[2] or b[1] != (expr["subroutine"] == "$signed"):
        return None
    return operand


def build_dependency_graph(ast: dict[str, Any], *, expected_top: str,
                           index: dict[str, Any] | None = None,
                           budget: AnalysisBudget = DEFAULT_BUDGET,
                           enable_width_conversions: bool = True,
                           enable_width_literals: bool = True,
                           enable_packed_coordinates: bool = True,
                           enable_bitwise: bool = True,
                           enable_mux: bool = True,
                           enable_dynamic: bool = True,
                           enable_selector_recovery: bool = True,
                           enable_typed_layout: bool = True,
                           enable_member_positions: bool = False) -> dict[str, Any]:
    """Bâtir des liens orientés source -> destination, à granularité signal.

    Les détails de sélection de bits et les effets combinatoires de primitives
    non reconnues ne sont pas déduits. Les avertissements explicitent ces limites.
    """
    ast_metrics = inspect_ast(ast, budget)
    structural = index if index is not None else build_index(ast, expected_top=expected_top)
    if structural.get("schema_version") != 1 or structural.get("top") != expected_top:
        raise ValueError("Index RTL v1 / top incohérent avec le graphe demandé")
    instances = {i["path"]: i for i in structural["instances"]}
    known: dict[str, set[str]] = {
        path: {p["name"] for p in inst["ports"]}
        for path, inst in instances.items()
    }
    for sig in structural["signals"]:
        if not sig.get("scope"):
            known[sig["instance_path"]].add(sig["name"])
    nodes = sorted(
        {f"{path}.{name}" for path, names in known.items() for name in names}
        | {(sig.get("path") or f"{sig['instance_path']}.{sig['name']}")
           for sig in structural["signals"]}
    )
    symbols = SignalResolver(ast, structural)
    node_set = set(nodes)
    # Only scalar declarations justify positional mapping of concatenated
    # lvalues. A vector named in a concatenation is NOT a one-bit operand.
    # The evidence comes from the elaborated index, not the source spelling.
    declared_types: dict[str, set[str]] = {}
    for owner, instance in instances.items():
        for port in instance["ports"]:
            declared_types.setdefault(f"{owner}.{port['name']}", set()).add(
                port.get("type") if isinstance(port.get("type"), str) else ""
            )
    for signal in structural["signals"]:
        name = signal.get("path") or f"{signal['instance_path']}.{signal['name']}"
        declared_types.setdefault(name, set()).add(
            signal.get("type") if isinstance(signal.get("type"), str) else ""
        )

    def single_bit(signal: str) -> bool:
        types = declared_types.get(signal, set())
        return bool(types) and all(
            value.strip() in ("logic", "bit", "reg") for value in types
        )

    direct_scalar_inputs: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, bool, str]] = set()
    warnings: list[dict[str, Any]] = []
    warning_keys: set[tuple[str, str]] = set()
    initializations: list[dict[str, Any]] = []
    static_selections: list[dict[str, Any]] = []
    selection_keys: set[tuple[str, str, str, str]] = set()

    # slang encodes references as "symbol-address symbol-name". The address
    # refers to the *exact* semantic declaration in the same exported AST.
    # Unlike ignoring names such as OPCODE_*, this is safe with shadowing.
    constant_declarations: dict[str, tuple[str, str]] = {}
    def collect_parameter_declarations(obj: Any) -> None:
        if isinstance(obj, list):
            for entry in obj:
                collect_parameter_declarations(entry)
        elif isinstance(obj, dict):
            if obj.get("kind") in ("Parameter", "EnumValue") and obj.get("addr") is not None:
                constant_declarations[str(obj["addr"])] = (
                    obj["kind"], str(obj.get("name", ""))
                )
            for key, value in obj.items():
                if key not in ("definition", "internalSymbol", "type") and isinstance(value, (dict, list)):
                    collect_parameter_declarations(value)

    collect_parameter_declarations(ast.get("design", {}))
    constant_refs_seen: set[str] = set()

    def warn(path: str, reason: str) -> None:
        key = (path, reason)
        if key not in warning_keys:
            warning_keys.add(key)
            warnings.append({"context": path, "reason": reason})

    def resolve(path: str, expr: Any) -> str | None:
        if not isinstance(expr, dict) or expr.get("kind") != "NamedValue":
            return None
        name = _symbol_name(expr)
        symbol = expr.get("symbol")
        reference_id = symbol.split(maxsplit=1)[0] if isinstance(symbol, str) else None
        if reference_id in constant_declarations:
            constant_refs_seen.add(reference_id)
            return None
        # slang explicitly marks some already evaluated parameters as constant;
        # use that semantic tag, never a name prefix or regex.
        if "constant" in expr and name not in known.get(path, set()):
            return None
        resolved = symbols.resolve(path, expr)
        if resolved is None:
            warn(path, f"Référence NamedValue inconnue/ambiguë : {name!r}")
        return resolved

    def constant_initializer_expression(path: str, expr: Any,
                                        depth: int = 0) -> bool:
        """Prove an initializer contains no runtime-signal reads.

        A 'constant' property on a live signal is not sufficient proof:
        only semantic Parameter/EnumValue IDs or non-signal constants count.
        """
        if not isinstance(expr, dict) or depth > 16:
            return False
        kind = expr.get("kind")
        if kind in ("IntegerLiteral", "UnbasedUnsizedIntegerLiteral",
                    "RealLiteral", "StringLiteral"):
            return True
        if kind == "NamedValue":
            symbol = expr.get("symbol")
            if not isinstance(symbol, str):
                return False
            address = symbol.split(maxsplit=1)[0]
            if address in constant_declarations:
                return True
            name = _symbol_name(expr)
            return "constant" in expr and name not in known.get(path, set())
        if kind == "MemberAccess":
            # A member of a proven constant object is also constant.
            # A 'constant' tag on a runtime signal is NOT such a proof.
            return (member_name(expr) is not None
                    and constant_initializer_expression(
                        path, expr.get("value"), depth + 1))
        if kind in ("Conversion", "SignedConversion", "UnaryOp"):
            return constant_initializer_expression(
                path, expr.get("operand"), depth + 1
            )
        if kind == "BinaryOp":
            return (constant_initializer_expression(path, expr.get("left"), depth + 1)
                    and constant_initializer_expression(path, expr.get("right"), depth + 1))
        if kind == "ElementSelect":
            return (constant_initializer_expression(path, expr.get("value"), depth + 1)
                    and constant_initializer_expression(path, expr.get("selector"), depth + 1))
        if kind == "RangeSelect":
            return (constant_initializer_expression(path, expr.get("value"), depth + 1)
                    and constant_initializer_expression(path, expr.get("left"), depth + 1)
                    and constant_initializer_expression(path, expr.get("right"), depth + 1))
        if kind == "Concatenation":
            parts = expr.get("operands")
            return (isinstance(parts, list) and 1 <= len(parts) <= 32
                    and all(constant_initializer_expression(path, part, depth + 1)
                            for part in parts))
        if kind == "Replication":
            return (constant_initializer_expression(path, expr.get("count"), depth + 1)
                    and constant_initializer_expression(path, expr.get("concat"), depth + 1))
        return False

    def static_index(path: str, expr: Any) -> int | None:
        """Use slang's elaborated constant only after proving no signal reads.

        Real generated indices contain Multiply/Add and compiler-reduced
        'constant' values. Re-parsing the source formula is not necessary.
        """
        if not constant_initializer_expression(path, expr):
            return None
        number = _static_integer(expr)
        if number is not None:
            return number
        if not isinstance(expr, dict):
            return None
        folded = expr.get("constant")
        if not isinstance(folded, (int, str)):
            return None
        return _static_integer({"kind": "IntegerLiteral", "value": folded})

    def record_selection(path: str, expr: dict[str, Any], role: str) -> None:
        """Trace static selections including nested array/part selections.

        No bit-level graph edges are inferred: metadata lists selectors from
        the base signal outward. Unknown or dynamic selectors still warn.
        """
        parts: list[dict[str, Any]] = []
        current: Any = expr
        for _ in range(6):
            if not isinstance(current, dict):
                break
            kind = current.get("kind")
            if kind == "ElementSelect":
                index = static_index(path, current.get("selector"))
                if index is None:
                    warn(path, "Sélection de bits/plage : dépendance au signal entier"
                         if role == "read" else
                         "Sélection de bits : dépendance au signal entier (approximation)")
                    return
                parts.append({"kind": "bit", "index": index})
            elif kind == "RangeSelect":
                left = static_index(path, current.get("left"))
                right = static_index(path, current.get("right"))
                if left is None or right is None or left < right:
                    warn(path, "Sélection de bits/plage : dépendance au signal entier"
                         if role == "read" else
                         "Sélection de bits : dépendance au signal entier (approximation)")
                    return
                parts.append({"kind": "range", "msb": left, "lsb": right})
            else:
                break
            current = current.get("value")
        if not parts:
            return
        if not isinstance(current, dict) or current.get("kind") != "NamedValue":
            warn(path, "Sélection imbriquée : dépendance au signal entier")
            return
        symbol = current.get("symbol")
        address = symbol.split(maxsplit=1)[0] if isinstance(symbol, str) else None
        if address in constant_declarations or (
            "constant" in current
            and _symbol_name(current) not in known.get(path, set())
        ):
            return
        signal = resolve(path, current)
        if signal is None:
            return  # resolve() already warned
        selection = (parts[0] if len(parts) == 1 else {
            "kind": "nested", "parts": list(reversed(parts))
        })
        key = (path, role, signal, str(selection))
        if key not in selection_keys:
            if len(static_selections) >= 2000:
                warn(path, "Preuves de sélections statiques tronquées (limite 2000)")
                return
            selection_keys.add(key)
            static_selections.append({
                "context": path, "role": role, "signal": signal,
                "selection": selection, "source": _location(expr),
            })

    def target(path: str, expr: Any) -> str | None:
        """Resolve MemberAccess writes conservatively to their *base* signal.

        A member lvalue never establishes a complete-vector or packed-field
        write. Combined member/part selections also cannot establish a flat
        bit position. Malformed tokens fail closed instead of resolving by
        field name; every accepted member write emits a coverage warning.
        """
        current = expr
        selections: list[dict[str, Any]] = []
        has_member = False
        for _ in range(16):
            if not isinstance(current, dict):
                warn(path, "Cible d'affectation non structurée")
                return None
            kind = current.get("kind")
            if kind == "NamedValue":
                resolved = resolve(path, current)
                if resolved is None and has_member:
                    warn(path, "Cible de membre : base RTL non résolue")
                    return None
                if has_member:
                    warn(path, "Écriture de membre : dépendance au signal entier (champs non localisés)")
                    if selections:
                        warn(path, "Sélection de membre : positions de bits non démontrées")
                else:
                    for sel in selections:
                        record_selection(path, sel, "write")
                return resolved
            if kind == "MemberAccess":
                if member_name(current) is None:
                    warn(path, "Cible MemberAccess malformée ou inconnue")
                    return None
                has_member = True
            elif kind in ("ElementSelect", "RangeSelect"):
                selections.append(current)
            else:
                warn(path, f"Cible non prise en charge : {kind}")
                return None
            current = current.get("value")
        warn(path, "Cible d'affectation trop profondément imbriquée")
        return None

    def reads(path: str, expr: Any) -> tuple[set[str], set[str]]:
        """(données, contrôle). Ne jamais chercher du RTL à l'aide de regex."""
        if not isinstance(expr, dict):
            return set(), set()
        kind = expr.get("kind")
        if kind == "NamedValue":
            ref = resolve(path, expr)
            return ({ref} if ref else set()), set()
        if kind in LITERALS:
            return set(), set()
        if kind == "MemberAccess":
            if member_name(expr) is None or not isinstance(expr.get("value"), dict):
                warn(path, "MemberAccess malformé : dépendances non démontrées")
                return set(), set()
            # For a runtime packed struct, the base signal is a *whole-
            # signal* dependency: never infer packed field offsets. For an
            # elaborated parameter/enum struct, resolve() ignores the base,
            # without fabricating a runtime edge from the member name.
            return reads(path, expr["value"])
        if kind in BINARY:
            left = reads(path, expr.get("left"))
            right = reads(path, expr.get("right"))
            return left[0] | right[0], left[1] | right[1]
        if kind in UNARY:
            return reads(path, expr.get("operand"))
        if kind in ("ElementSelect", "RangeSelect"):
            # Granularité signal entier : les indices sont des sources de données
            # potentielles (quel bit est lu), pas des signaux à indexer.
            base = reads(path, expr.get("value"))
            selectors = [expr.get("selector")] if kind == "ElementSelect" else [
                expr.get("left"), expr.get("right")
            ]
            data, control = set(base[0]), set(base[1])
            for selector_expr in selectors:
                sel_data, sel_control = reads(path, selector_expr)
                data.update(sel_data | sel_control)
            record_selection(path, expr, "read")
            return data, control
        if kind == "Replication":
            # slang v12.1: {N{expression}} -> Replication(count, concat).
            # Le nombre de répétitions est normalement une constante
            # d'élaboration ; conserver une dépendance si l'AST en indique une.
            content = expr.get("concat")
            if not isinstance(content, dict):
                warn(path, "Replication sans concaténation valide")
                return set(), set()
            data, control = reads(path, content)
            number_data, number_control = reads(path, expr.get("count"))
            return data | number_data, control | number_control
        if kind == "Concatenation":
            operands = expr.get("operands")
            if not isinstance(operands, list):
                warn(path, "Concatenation sans liste d'opérandes")
                return set(), set()
            data: set[str] = set()
            control: set[str] = set()
            for operand in operands:
                operand_data, operand_control = reads(path, operand)
                data.update(operand_data)
                control.update(operand_control)
            return data, control
        if kind == "Call":
            operand = _sign_cast_operand(expr)
            if operand is not None:
                return reads(path, operand)
        if kind == "ConditionalOp":
            cond_refs: set[str] = set()
            for condition in expr.get("conditions", []):
                if isinstance(condition, dict):
                    d, c = reads(path, condition.get("expr"))
                    cond_refs.update(d | c)
            a = reads(path, expr.get("left"))
            b = reads(path, expr.get("right"))
            return a[0] | b[0], cond_refs | a[1] | b[1]
        warn(path, f"Expression non prise en charge : {kind}")
        return set(), set()

    def add(source: str, dest: str, kind: str, context: dict[str, Any],
            *, sequential: bool = False, detail: str = "") -> None:
        if source not in node_set or dest not in node_set:
            warn(dest, f"Arête ignorée : symbole inconnu {source} -> {dest}")
            return
        key = (source, dest, kind, sequential, detail)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"source": source, "target": dest, "kind": kind,
                          "sequential": sequential, "detail": detail,
                          "location": _location(context)})

    def _explicit_literal_width(node: dict[str, Any]) -> int | None:
        # Slang's literal value (for example 3'h0) carries an explicit size.
        # Unsized constants cannot establish a one-bit lane mapping.
        value = node.get("value")
        if not isinstance(value, str):
            return None
        import re
        match = re.fullmatch(r"([0-9]{1,3})'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+", value)
        if match is None:
            return None
        width = int(match.group(1))
        return width if 1 <= width <= 32 else None

    def source_free_literal(node: Any, depth: int = 0) -> bool:
        """Only transparent conversions of literal AST nodes are source-free.

        Slang 12.1 wraps the rxuart reset value in Conversion(operand=
        IntegerLiteral). A "constant" tag alone is not a reason to discard
        signal reads; the operand must be proved to be a literal.
        """
        if not isinstance(node, dict) or depth > 4:
            return False
        kind = node.get("kind")
        if kind in ("IntegerLiteral", "UnbasedUnsizedIntegerLiteral"):
            return True
        if kind in ("Conversion", "SignedConversion"):
            return source_free_literal(node.get("operand"), depth + 1)
        return False

    def concatenated_assignment(path: str, obj: dict[str, Any], *,
                                controls: frozenset[str],
                                events: tuple[tuple[str, str], ...],
                                sequential: bool) -> None:
        """Conservative, one-bit positional mapping for a concatenated lvalue.

        Every resolved lvalue receives control/event edges. Data edges are
        emitted only for a provably one-bit positional match, never as an
        all-to-all approximation across RHS operands of unknown widths.
        """
        lhs = obj["left"]
        operands = lhs.get("operands")
        if not isinstance(operands, list) or not 1 <= len(operands) <= 32:
            warn(path, "Concaténation cible vide, malformée ou trop grande")
            return
        destinations: list[str] = []
        for operand in operands:
            if not isinstance(operand, dict) or operand.get("kind") != "NamedValue":
                warn(path, "Concaténation cible : opérande non pris en charge")
                return
            dest = resolve(path, operand)
            if dest is None:
                warn(path, "Concaténation cible : signal non résolu")
                return
            destinations.append(dest)

        # A whole-signal reference has no inferable lane unless its elaborated
        # declared type is explicitly scalar. Only a fully aligned N-bit RHS
        # gets N independent data edges.
        paired: list[str | None] | None = None
        rhs = obj.get("right")
        if source_free_literal(rhs):
            # A literal never reads an RTL signal. Its width may be extended
            # or truncated on assignment, but data dependency edges remain
            # empty regardless of that conversion. No bit mapping is claimed.
            paired = [None] * len(destinations)
        elif all(single_bit(dest) for dest in destinations) and isinstance(rhs, dict):
            rhs_kind = rhs.get("kind")
            if rhs_kind == "Concatenation":
                values = rhs.get("operands")
                if isinstance(values, list) and len(values) == len(destinations):
                    mapped: list[str | None] = []
                    for operand in values:
                        if not isinstance(operand, dict):
                            break
                        if operand.get("kind") == "NamedValue":
                            source = resolve(path, operand)
                            if source is None or not single_bit(source):
                                break
                            mapped.append(source)
                        elif operand.get("kind") == "IntegerLiteral" and (
                            _explicit_literal_width(operand) == 1
                        ):
                            mapped.append(None)
                        else:
                            break
                    if len(mapped) == len(destinations):
                        paired = mapped
        if paired is None:
            warn(path, "Concaténation cible : positions RHS non démontrées (données omises)")
        for i, dest in enumerate(destinations):
            if paired is not None and paired[i] is not None:
                add(paired[i], dest, "data", obj, sequential=sequential)
            for source in sorted(controls):
                add(source, dest, "control", obj, sequential=sequential)
            for source, edge in events:
                add(source, dest, "event", obj, sequential=sequential, detail=edge)

    def assignment(path: str, obj: Any, *, controls: frozenset[str] = frozenset(),
                   events: tuple[tuple[str, str], ...] = (), sequential: bool = False) -> None:
        if not isinstance(obj, dict) or obj.get("kind") != "Assignment":
            warn(path, "Affectation non reconnue")
            return
        lhs = obj.get("left")
        if isinstance(lhs, dict) and lhs.get("kind") == "Concatenation":
            concatenated_assignment(path, obj, controls=controls,
                                    events=events, sequential=sequential)
            return
        dst = target(path, lhs)
        if dst is None:
            return
        values, expression_controls = reads(path, obj.get("right"))
        for source in sorted(values):
            add(source, dst, "data", obj, sequential=sequential)
        for source in sorted(set(controls) | expression_controls):
            add(source, dst, "control", obj, sequential=sequential)
        for source, edge in events:
            add(source, dst, "event", obj, sequential=sequential, detail=edge)

    def statements(path: str, obj: Any, *, controls: frozenset[str] = frozenset(),
                   events: tuple[tuple[str, str], ...] = (), sequential: bool = False) -> None:
        if isinstance(obj, list):
            for child in obj:
                statements(path, child, controls=controls, events=events,
                           sequential=sequential)
            return
        if not isinstance(obj, dict):
            return
        kind = obj.get("kind")
        if kind == "ExpressionStatement":
            assignment(path, obj.get("expr"), controls=controls,
                       events=events, sequential=sequential)
        elif kind == "Block":
            stmts = obj.get("body")
            if isinstance(stmts, list):
                for child in stmts:
                    statements(path, child, controls=controls, events=events,
                               sequential=sequential)
            else:
                statements(path, stmts, controls=controls, events=events,
                           sequential=sequential)
        elif kind == "List":
            # Vrai slang v12.1 : les séquences begin/end contenant plusieurs
            # instructions sont exportées avec kind=List et une clé "list".
            children = obj.get("list")
            if not isinstance(children, list):
                warn(path, "List sans liste d'instructions valide")
            else:
                statements(path, children, controls=controls, events=events,
                           sequential=sequential)
        elif kind == "StatementList":
            for child in obj.get("statements", []):
                statements(path, child, controls=controls, events=events,
                           sequential=sequential)
        elif kind == "Conditional":
            control = set(controls)
            for cond in obj.get("conditions", []):
                if isinstance(cond, dict):
                    d, c = reads(path, cond.get("expr"))
                    control.update(d | c)
            nested = frozenset(control)
            statements(path, obj.get("ifTrue"), controls=nested,
                       events=events, sequential=sequential)
            statements(path, obj.get("ifFalse"), controls=nested,
                       events=events, sequential=sequential)
        elif kind == "Case":
            if obj.get("condition") != "Normal":
                warn(path, f"Case à comparaisons spéciales non couvert : {obj.get('condition')}")
            control = set(controls)
            expr_data, expr_control = reads(path, obj.get("expr"))
            control.update(expr_data | expr_control)
            items = obj.get("items")
            if not isinstance(items, list):
                warn(path, "Case sans liste de branches")
                return
            # Une expression d'étiquette peut elle-même dépendre de variables.
            # Elles participent à la décision de sélection de branche.
            all_label_refs: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    warn(path, "Branche case malformée")
                    continue
                labels = item.get("expressions")
                if not isinstance(labels, list):
                    warn(path, "Étiquettes case malformées")
                    continue
                for label in labels:
                    d, c = reads(path, label)
                    all_label_refs.update(d | c)
            case_controls = frozenset(control | all_label_refs)
            for item in items:
                if isinstance(item, dict):
                    statements(path, item.get("stmt"), controls=case_controls,
                               events=events, sequential=sequential)
            statements(path, obj.get("defaultCase"), controls=case_controls,
                       events=events, sequential=sequential)
        elif kind == "Timed":
            extracted: list[tuple[str, str]] = list(events)
            timing = obj.get("timing")
            if not isinstance(timing, dict):
                warn(path, "Timing absent ou non structuré")
            elif timing.get("kind") == "ImplicitEvent":
                # slang: always @* / implicit combinational sensitivity.
                # Its signal-level influences are already carried by reads()
                # and conditional guards. Do NOT invent clock/event edges.
                if sequential:
                    warn(path, "Sensibilité implicite inattendue dans always_ff")
            else:
                event_nodes: list[Any] = []
                if timing.get("kind") == "SignalEvent":
                    # slang 12.1 also emits a *direct* single SignalEvent,
                    # not necessarily an EventList wrapper.
                    event_nodes = [timing]
                elif timing.get("kind") == "EventList":
                    sequence = timing.get("events")
                    if isinstance(sequence, list) and sequence:
                        event_nodes = sequence
                    else:
                        warn(path, "EventList vide ou malformée")
                else:
                    warn(path, f"Timing non pris en charge : {timing.get('kind')}")
                for event in event_nodes:
                    if not isinstance(event, dict) or event.get("kind") != "SignalEvent":
                        warn(path, "Événement temporel non pris en charge")
                        continue
                    edge = event.get("edge")
                    # A generic @signal is not equivalent to posedge/negedge.
                    # Keep unsupported timing explicit rather than guessing.
                    if edge not in ("PosEdge", "NegEdge"):
                        warn(path, f"Front SignalEvent non pris en charge : {edge!r}")
                        continue
                    reference = resolve(path, event.get("expr"))
                    if reference is None:
                        warn(path, "SignalEvent sans référence de signal résolue")
                        continue
                    extracted.append((reference, edge))
            # always @(posedge clk) is sequential even if slang labels its
            # ProcedureKind as Always rather than AlwaysFF.
            edge_triggered = any(
                edge in ("PosEdge", "NegEdge") for _, edge in extracted
            )
            statements(path, obj.get("stmt"), controls=controls,
                       events=tuple(extracted),
                       sequential=sequential or edge_triggered)
        elif kind in ("Empty", "EmptyStatement"):
            pass
        else:
            warn(path, f"Instruction non prise en charge : {kind}")

    def initial_statements(path: str, body: Any, depth: int = 0
                           ) -> list[dict[str, Any]] | None:
        """Accept only constant, direct-lvalue initial assignments.

        Initial values are metadata, NEVER data, clock or reset graph edges.
        A partially unsupported initial block is rejected atomically.
        """
        if not isinstance(body, dict) or depth > 16:
            return None
        kind = body.get("kind")
        if kind in ("Block", "List", "StatementList"):
            field = ("body" if kind == "Block"
                     else "list" if kind == "List" else "statements")
            children = body.get(field)
            if isinstance(children, dict):
                children = [children]
            if not isinstance(children, list) or len(children) > 256:
                return None
            found: list[dict[str, Any]] = []
            for child in children:
                child_rows = initial_statements(path, child, depth + 1)
                if child_rows is None:
                    return None
                found.extend(child_rows)
            return found
        if kind != "ExpressionStatement":
            return None
        assign = body.get("expr")
        if not isinstance(assign, dict) or assign.get("kind") != "Assignment":
            return None
        lhs, rhs = assign.get("left"), assign.get("right")
        if not isinstance(lhs, dict) or lhs.get("kind") != "NamedValue":
            return None
        if not constant_initializer_expression(path, rhs):
            return None
        destination = resolve(path, lhs)
        if destination is None:
            return None
        return [{
            "target": destination, "source": _location(assign),
            "expression_kind": rhs.get("kind"),
            "scope": "initial_only_not_runtime",
        }]

    def connections(node: dict[str, Any], path: str, parent: str | None) -> None:
        if parent is None:
            return
        for connection in node.get("connections", []):
            if not isinstance(connection, dict):
                continue
            port = connection.get("port")
            expr = connection.get("expr")
            if not isinstance(port, dict) or not isinstance(port.get("name"), str):
                warn(path, "Connexion sans port identifiable")
                continue
            local = f"{path}.{port['name']}"
            direction = port.get("direction")
            if direction == "In":
                data, control = reads(parent, expr)
                # Only direct elaborated scalar input connections are candidates
                # for event identity. General port edges are not aliases.
                if isinstance(expr, dict) and expr.get("kind") == "NamedValue":
                    direct = resolve(parent, expr)
                    if direct in node_set and local in node_set and single_bit(direct) and single_bit(local) and data == {direct} and not control:
                        direct_scalar_inputs.append({"source": direct, "target": local,
                                                     "location": _location(expr)})
                for source in sorted(data | control):
                    add(source, local, "port_input", expr if isinstance(expr, dict) else port)
            elif direction == "Out":
                # slang fournit habituellement un Assignment(left=<lvalue>, right=EmptyArgument)
                lhs = expr.get("left") if isinstance(expr, dict) and expr.get("kind") == "Assignment" else expr
                dest = target(parent, lhs)
                if dest:
                    add(local, dest, "port_output", expr if isinstance(expr, dict) else port)
            else:
                warn(path, f"Port {port['name']} direction {direction} non prise en charge")

    visited_instances: set[str] = set()

    def visit(members: list[Any], parent: str | None = None) -> None:
        for node in members:
            if not isinstance(node, dict):
                continue
            if node.get("kind") in ("GenerateBlock", "GenerateBlockArray", "Scope"):
                # Les branches inactives ne font pas partie du matériel élaboré.
                if node.get("isUninstantiated") is True:
                    continue
                nested = node.get("members")
                if isinstance(nested, list):
                    visit(nested, parent)
                else:
                    warn(parent or expected_top, "Scope non indexable dans le graphe")
                continue
            if node.get("kind") == "ContinuousAssign" and parent is not None:
                assignment(parent, node.get("assignment"))
                continue
            if node.get("kind") == "ProceduralBlock" and parent is not None:
                procedure_kind = node.get("procedureKind")
                if procedure_kind == "Initial":
                    records = initial_statements(parent, node.get("body"))
                    if records is None:
                        warn(parent, "Procédure non prise en charge : Initial")
                    elif len(initializations) + len(records) > 2000:
                        warn(parent, "Initialisations constantes tronquées (limite 2000)")
                    else:
                        initializations.extend(records)
                elif procedure_kind in ("AlwaysFF", "AlwaysComb", "AlwaysLatch", "Always"):
                    statements(parent, node.get("body"),
                               sequential=(procedure_kind == "AlwaysFF"))
                else:
                    warn(parent, f"Procédure non prise en charge : {procedure_kind}")
                continue
            if node.get("kind") != "Instance":
                continue
            path = f"{parent}.{node['name']}" if parent else node["name"]
            if path not in instances:
                raise ValueError(f"Instance non indexée : {path}")
            visited_instances.add(path)
            connections(node, path, parent)
            body = node["body"]
            visit(body["members"], path)

    visit(ast["design"]["members"])
    for missing_path in sorted(set(instances) - visited_instances):
        warn(missing_path, "Instance connue de l'index mais absente du graphe")
    edges.sort(key=lambda x: (x["target"], x["source"], x["kind"], x["detail"]))
    initializations.sort(key=lambda x: (
        x["target"], str(x["source"]), x["expression_kind"]
    ))
    static_selections.sort(key=lambda x: (
        x["context"], x["role"], x["signal"], str(x["selection"])
    ))
    warnings.sort(key=lambda x: (x["context"], x["reason"]))
    captured_assignments=[] if enable_packed_coordinates or enable_bitwise or enable_mux or enable_dynamic else None
    graph = {
        "schema_version": GRAPH_SCHEMA_VERSION, "backend": "slang-ast-json",
        "top": expected_top, "nodes": nodes, "edges": edges,
        "initializations": initializations,
        "static_selections": static_selections,
        "counts": {"nodes": len(nodes), "edges": len(edges), "warnings": len(warnings)},
        "warnings": warnings,
        "expressions": build_expression_index(ast, expected_top=expected_top, index=structural,
                                              row_limit=budget.expression_rows),
        "register_flow": build_register_flow(ast, expected_top=expected_top, index=structural),
        "bit_accesses": build_bit_access_index(ast, expected_top=expected_top, index=structural,
                                              enable_width_conversions=enable_width_conversions,
                                              enable_width_literals=enable_width_literals,
                                              captured_assignments=captured_assignments),
        "resolved_parameter_symbols": sorted(
            constant_declarations[addr][1] for addr in constant_refs_seen
            if constant_declarations[addr][0] == "Parameter"
        ),
        "resolved_enum_symbols": sorted(
            constant_declarations[addr][1] for addr in constant_refs_seen
            if constant_declarations[addr][0] == "EnumValue"
        ),
        "limitations": [
            "Dépendances conservatrices au niveau signal, sans granularité bit",
            "Initialisations constantes recensées séparément, sans arêtes d'exécution",
            "Sélections statiques décrites en métadonnées, sans arêtes bit-à-bit",
            "Case normal, concaténations, sélections et generate if simples seulement",
            "Appels système $signed/$unsigned intégraux de largeur identique : références signal uniquement ; autres fonctions, tâches, casez/casex et generate complexes non résolus",
            "Événements toujours classés event : horloge versus reset non inférés",
            "Le graphe peut être incomplet si des avertissements sont présents",
            "Pas de preuve fonctionnelle, timing ou CDC",
        ],
    }
    graph["complex_constructs"] = build_complex_construct_index(ast, index=structural, row_limit=budget.complex_rows)
    graph["bit_dependency_graph"] = build_bit_dependency_graph(graph["bit_accesses"], structural)
    graph["function_dependencies"] = build_function_dependencies(ast, index=structural)
    graph["static_loop_expansion"] = build_static_loop_expansion(ast, index=structural)
    graph["array_dependencies"] = build_array_dependencies(ast, index=structural, captured_assignments=captured_assignments if enable_packed_coordinates else None)
    graph["bitwise_dependencies"] = build_bitwise_dependencies(ast, structural, captured_assignments,
        graph["bit_dependency_graph"], enabled=enable_bitwise)
    graph["mux_dependencies"] = build_mux_dependencies(ast, structural, captured_assignments,
        graph["bit_dependency_graph"], enabled=enable_mux)
    graph["dynamic_dependencies"] = build_dynamic_dependencies(ast, structural, captured_assignments,
        graph["bit_dependency_graph"], enabled=enable_dynamic)
    graph["selector_recovery"] = build_selector_recovery(ast, structural, captured_assignments,
        graph["bit_dependency_graph"], graph["dynamic_dependencies"], enabled=enable_selector_recovery and enable_dynamic)
    graph["typed_layout"] = build_typed_layout(ast, structural, captured_assignments,
        graph["bit_dependency_graph"], graph["dynamic_dependencies"], enabled=enable_typed_layout and enable_dynamic)
    graph["coverage"] = build_coverage_summary(graph)
    graph["sequential_candidates"] = build_sequential_candidates(graph["register_flow"])
    graph["intercycle_dependencies"] = build_intercycle_dependencies(graph["sequential_candidates"])
    graph["hierarchical_event_bindings"] = {
        "schema_version": 1, "scope": "direct_scalar_input_port_candidates",
        "items": sorted(direct_scalar_inputs, key=lambda x: (x["target"], x["source"])),
    }
    if enable_member_positions:
        from .member_positions import build_member_positions
        graph["member_position_candidates"] = build_member_positions(ast, structural, graph)
    graph["analysis_limits"] = build_analysis_limits(graph, ast_metrics, budget)
    return graph


def trace_dependencies(graph: dict[str, Any], node: str, direction: str = "fanin",
                       *, max_depth: int = 3, max_edges: int = 200) -> dict[str, Any]:
    """Parcours en largeur borné et robuste aux cycles ; zéro inférence LLM."""
    if graph.get("schema_version") != GRAPH_SCHEMA_VERSION:
        raise ValueError("Version de graphe inconnue")
    if direction not in ("fanin", "fanout"):
        raise ValueError("Direction attendue : fanin ou fanout")
    if not 0 <= max_depth <= 15 or not 1 <= max_edges <= 5000:
        raise ValueError("Limites de recherche invalides")
    if node not in set(graph["nodes"]):
        raise KeyError(f"Signal inconnu dans le graphe : {node}")
    adjacency: dict[str, list[dict[str, Any]]] = {}
    lookup = "target" if direction == "fanin" else "source"
    next_key = "source" if direction == "fanin" else "target"
    for edge in graph["edges"]:
        adjacency.setdefault(edge[lookup], []).append(edge)
    queue = deque([(node, 0)])
    visited = {node}
    used_edges: set[tuple[str, str, str, str]] = set()
    found: list[dict[str, Any]] = []
    truncated = False
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in adjacency.get(current, []):
            key = (edge["source"], edge["target"], edge["kind"], edge.get("detail", ""))
            if key not in used_edges:
                if len(found) >= max_edges:
                    truncated = True
                    break
                used_edges.add(key)
                found.append({**edge, "depth": depth + 1})
            neighbor = edge[next_key]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
        if truncated:
            break
    return {"query": node, "direction": direction, "max_depth": max_depth,
            "edges": found, "visited_nodes": sorted(visited), "truncated": truncated,
            "graph_warnings": graph.get("warnings", [])}
