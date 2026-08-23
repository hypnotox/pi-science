# pyright: reportPrivateUsage=false, reportUnusedImport=false
"""Compatibility facade for formula service entry points."""

from ._analysis.computation import (
    MAX_COMBINED_RESULT_BYTES,
    MAX_OPTIMIZATION_BYTES,
    MAX_RESULT_BYTES,
    analyze_retained,
)
from ._service.optimization import optimize
from ._service.orchestration import analyze, analyze_dominance
from ._service.query_execution import _attach_queries, _compose_derived_qualification
from ._service.result_bounds import _bound_optimization_result, _bound_result

# Characterized private compatibility alias; neutral analysis owns implementation.
_analyze_computation = analyze_retained

__all__ = (
    "MAX_COMBINED_RESULT_BYTES",
    "MAX_OPTIMIZATION_BYTES",
    "MAX_RESULT_BYTES",
    "_analyze_computation",
    "_attach_queries",
    "_bound_optimization_result",
    "_bound_result",
    "_compose_derived_qualification",
    "analyze",
    "analyze_dominance",
    "optimize",
)
