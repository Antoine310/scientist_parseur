"""Global JSON-size gates and explicit observed analyzer-limit diagnostics.

These are admission / publication gates, not a process memory or CPU quota.
The per-analyzer traversal and record limits remain authoritative.
"""
from collections import Counter
from dataclasses import asdict, dataclass
import json

from .row_budgets import effective_row_limit
from . import expressions, flow, bitaccess, bitgraph, sequential, intercycle
from . import complex_constructs, function_dependencies, static_loops, array_dependencies, bitwise_dependencies, mux_dependencies

@dataclass(frozen=True)
class AnalysisBudget:
    max_ast_bytes: int = 256 * 1024 * 1024
    max_ast_values: int = 3_000_000
    max_ast_depth: int = 128
    max_graph_values: int = 5_000_000
    max_graph_depth: int = 128
    expression_rows: int | None = None
    complex_rows: int | None = None

    def __post_init__(self):
        for name,value in asdict(self).items():
            if name in ("expression_rows", "complex_rows"):
                effective_row_limit(value, 4096)
                continue
            if type(value) is not int or value < 1:
                raise ValueError("invalid analysis budget: "+name)
        if self.max_ast_depth>256 or self.max_graph_depth>256:
            raise ValueError("analysis depth limit must not exceed 256")

DEFAULT_BUDGET=AnalysisBudget()

class AnalysisBudgetError(ValueError):
    def __init__(self,stage,metric,limit,observed):
        self.details={"stage":stage,"metric":metric,"limit":limit,
                      "observed_at_least":observed}
        super().__init__(f"{stage}: {metric} budget exceeded ({observed} > {limit})")

def measure_tree(root,*,stage,max_values,max_depth):
    """Count JSON values (including containers, excluding keys), root depth 0.

    Iterator stack is O(depth), never enqueue every member of a wide list.
    Repeated objects count per occurrence, as they do in serialized JSON.
    Stop immediately on the first exceeded bound.
    """
    stack=[(iter((root,)),0)]
    values=0
    deepest=0
    while stack:
        children,depth=stack[-1]
        try:
            node=next(children)
        except StopIteration:
            stack.pop()
            continue
        values+=1
        if values>max_values:
            raise AnalysisBudgetError(stage,"json_values",max_values,values)
        if depth>max_depth:
            raise AnalysisBudgetError(stage,"json_depth",max_depth,depth)
        deepest=max(deepest,depth)
        if isinstance(node,dict):
            stack.append((iter(node.values()),depth+1))
        elif isinstance(node,(list,tuple)):
            stack.append((iter(node),depth+1))
    return {"json_values":values,"json_depth":deepest}

def inspect_ast(ast,budget=DEFAULT_BUDGET):
    return measure_tree(ast,stage="ast_admission",max_values=budget.max_ast_values,
                        max_depth=budget.max_ast_depth)

def read_ast(path,budget=DEFAULT_BUDGET):
    # The file-size gate precedes decoding, including a bounded read if the
    # file grows after stat(). slang's own allocation precedes this gate.
    size=path.stat().st_size
    if size>budget.max_ast_bytes:
        raise AnalysisBudgetError("ast_admission","file_bytes",budget.max_ast_bytes,size)
    with path.open("rb") as stream:
        raw=stream.read(budget.max_ast_bytes+1)
    if len(raw)>budget.max_ast_bytes:
        raise AnalysisBudgetError("ast_admission","file_bytes",budget.max_ast_bytes,len(raw))
    try:
        ast=json.loads(raw.decode("utf-8"))
    except RecursionError as exc:
        raise ValueError("AST JSON decoder recursion limit exceeded") from exc
    inspect_ast(ast,budget)
    return ast

# Read the actual constants, rather than duplicate numeric policy.
ANALYZERS={
    "expressions":(expressions,"captured",("MAX_EXPRESSIONS","MAX_TREE_NODES","MAX_DEPTH","MAX_STATEMENT_DEPTH","MAX_GUARDS","MAX_EVENTS")),
    "register_flow":(flow,"captured",("MAX_PROCESSES","MAX_TARGETS","MAX_PATHS","MAX_STATEMENTS","MAX_DEPTH","MAX_GUARDS","MAX_WRITES_PER_PATH","MAX_CONDITION_DEPTH","MAX_CONDITION_NODES","MAX_PROBE_NODES")),
    "bit_accesses":(bitaccess,"captured",("MAX_RECORDS","MAX_SEGMENTS","MAX_DEPTH","MAX_WIDTH","MAX_NODES","MAX_PROC_DEPTH","MAX_PROC_STATEMENTS","MAX_PROC_GUARDS","MAX_PROC_EVENTS")),
    "bit_dependency_graph":(bitgraph,"assignments",("MAX_EDGES","MAX_WIDTH")),
    "complex_constructs":(complex_constructs,"captured",("MAX_NODES","MAX_ROWS","MAX_DEPTH","MAX_ARGS","MAX_REFS","MAX_REPEAT")),
    "function_dependencies":(function_dependencies,"captured",("MAX_ARGS","MAX_NODES","MAX_DEPTH","MAX_ROWS","MAX_SCAN")),
    "static_loop_expansion":(static_loops,"captured",("MAX_ITERATIONS","MAX_ROWS","MAX_EDGES","MAX_SCAN","MAX_DEPTH")),
    "array_dependencies":(array_dependencies,"captured",("MAX_DIMENSIONS","MAX_WIDTH","MAX_ROWS","MAX_EDGES","MAX_SCAN","MAX_DEPTH")),
    "bitwise_dependencies":(bitwise_dependencies,"captured",("MAX_ROWS","MAX_EDGES","MAX_WIDTH","MAX_DEPTH","MAX_NODES","MAX_ROW_PAIRS")),
    "mux_dependencies":(mux_dependencies,"captured",("MAX_ROWS","MAX_EDGES","MAX_WIDTH","MAX_DEPTH","MAX_NODES","MAX_BRANCHES","MAX_ROW_PAIRS")),
    "sequential_candidates":(sequential,"captured",("MAX_PATHS_PER_TARGET","MAX_WRITES_PER_PATH")),
    "intercycle_dependencies":(intercycle,"captured",("MAX_ROWS","MAX_REFERENCES","MAX_DEPTH")),
}

INHERITED_FROM={
    "bit_dependency_graph":"bit_accesses",
    "sequential_candidates":"register_flow",
    "intercycle_dependencies":"sequential_candidates",
}
EXCLUSION_FIELDS=("unsupported_targets","unsupported_statements",
                  "procedural_blocks_skipped","partial_processes")
MAX_REASON_LENGTH=160

def natural(value,name):
    if type(value) is not int or value<0:
        raise ValueError("invalid analyzer count: "+name)
    return value

def nested_truncated(row):
    stack=[row]
    while stack:
        obj=stack.pop()
        if isinstance(obj,dict):
            if obj.get("truncated") is True:
                return True
            stack.extend(v for v in obj.values() if isinstance(v,(dict,list)))
        elif isinstance(obj,list):
            stack.extend(v for v in obj if isinstance(v,(dict,list)))
    return False

def analyzer_summary(graph):
    reports={}
    for name,(module,counter,limit_names) in ANALYZERS.items():
        # Stored graph v1 artifacts predating PR72 did not have this channel.
        if name in ("bitwise_dependencies","mux_dependencies") and name not in graph:
            continue
        data=graph.get(name)
        if not isinstance(data,dict) or data.get("schema_version")!=1:
            raise ValueError("missing analyzer v1: "+name)
        items,counts=data.get("items"),data.get("counts")
        if not isinstance(items,list) or not isinstance(counts,dict):
            raise ValueError("malformed analyzer: "+name)
        captured=natural(counts.get(counter),name+"."+counter)
        if captured!=len(items) or type(counts.get("truncated")) is not bool:
            raise ValueError("inconsistent analyzer counts: "+name)
        status=Counter()
        reasons=Counter()
        nested=0
        for row in items:
            if not isinstance(row,dict):
                raise ValueError("malformed analyzer row: "+name)
            coverage=row.get("coverage")
            if not isinstance(coverage,str) or not coverage:
                coverage="unknown"
            status[coverage]+=1
            if coverage=="partial":
                reasons[str(row.get("reason") or "partial_record")[:MAX_REASON_LENGTH]]+=1
            nested+=nested_truncated(row)
        exclusions={k:natural(counts[k],name+"."+k) for k in EXCLUSION_FIELDS if k in counts}
        upstream=INHERITED_FROM.get(name)
        inherited=bool(upstream and graph[upstream]["counts"]["truncated"])
        configured={k:getattr(module,k) for k in limit_names}
        row_key={"expressions":"MAX_EXPRESSIONS","complex_constructs":"MAX_ROWS"}.get(name)
        if row_key is not None and "row_limit" in data:
            if data["row_limit"] is None:
                raise ValueError("missing effective row limit: "+name)
            configured[row_key]=effective_row_limit(data["row_limit"],configured[row_key])
            if captured>configured[row_key]:
                raise ValueError("captured rows exceed effective limit: "+name)
        reports[name]={"scope":data.get("scope"),"captured":captured,
                       "status_counts":dict(sorted(status.items())),
                       "partial_reasons":dict(sorted(reasons.items())),
                       "truncated":counts["truncated"],
                       "rows_with_nested_truncation":nested,
                       "upstream_truncation":upstream if inherited else None,
                       "exclusion_counts":exclusions,
                       "configured_limits":configured}
    truncated=[name for name,r in reports.items() if r["truncated"] or
               r["rows_with_nested_truncation"] or r["upstream_truncation"]]
    limited=[name for name,r in reports.items() if name in truncated or
             r["status_counts"].get("partial",0) or r["status_counts"].get("unknown",0)
             or any(r["exclusion_counts"].values())]
    coverage=graph["coverage"]
    findings_truncated=coverage["findings_truncated"]
    return {"analyzers":reports,"truncated_analyzers":truncated,"limited_analyzers":limited,
            "signal_graph_warnings":len(graph["warnings"]),
            "coverage_findings_truncated":findings_truncated,
            "assessment":"reported_truncation" if truncated else
                "reported_limits" if limited or graph["warnings"] or findings_truncated
                else "no_reported_limits_within_observed_scopes"}

def build_analysis_limits(graph,ast_metrics,budget=DEFAULT_BUDGET):
    # Publication gate before emitting the graph. It does not prevent the
    # intermediate graph allocation and is not a serialized-byte limit.
    metrics=measure_tree(graph,stage="graph_publication",max_values=budget.max_graph_values,
                         max_depth=budget.max_graph_depth)
    return {"schema_version":1,"scope":"observed_analyzer_limits_and_json_gates",
            "policy":asdict(budget),"ast_metrics":ast_metrics,
            "graph_metrics_excluding_this_report":metrics,
            **analyzer_summary(graph),"design_coverage":"not_measured",
            "functional_influence":"not_proven",
            "caveat":"Observed counters, not a common denominator or whole-design coverage. "
                     "JSON gates are not CPU/memory limits. Some analyzer exclusions are not inventoried."}
