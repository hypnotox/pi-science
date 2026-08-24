# pyright: reportPrivateUsage=false
"""Service-owned explicit optimization dispatch."""

from __future__ import annotations

from py_science.formula._analysis.computation import analyze_retained
from py_science.formula._optimization.search import _optimization_result
from py_science.formula.contracts.goals import OptimizationFailure, OptimizeOutcome
from py_science.formula.models import AnalysisFailure, AnalysisRequest, OptimizeRequest

from .result_bounds import _bound_optimization_result


def optimize(request: OptimizeRequest) -> OptimizeOutcome:
    try:
        excluded = {"operation", "goal", "search", "proof", "projection_limit"}
        ordinary = request.model_dump(exclude=excluded)
        computed = analyze_retained(AnalysisRequest.model_validate(ordinary))
        if isinstance(computed, AnalysisFailure):
            return OptimizationFailure(error=computed.error.message)
        result = _optimization_result(
            request, computed, computed.work_context, analyzer=analyze_retained
        )
        return _bound_optimization_result(result)
    except Exception:
        return OptimizationFailure(error="optimization operation failed unexpectedly")
