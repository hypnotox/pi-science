# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Service-owned ordinary and direct optimization dispatch."""

from __future__ import annotations

from py_science.formula._analysis.computation import analyze_retained
from py_science.formula._optimization.search import _optimization_report
from py_science.formula.models import (
    AnalysisFailure,
    AnalysisRequest,
    OptimizationFailure,
    OptimizationSuccess,
    OptimizeOutcome,
    OptimizeRequest,
)

from .result_bounds import _bound_optimization_result


def optimize(request: OptimizeRequest) -> OptimizeOutcome:
    """Run the same bounded Python policy exposed by ordinary advice."""
    try:
        ordinary = AnalysisRequest.model_validate(
            {
                "syntax": request.syntax,
                "expression": request.expression,
                "equations": request.equations,
                "variables": request.variables,
                "functions": request.functions,
                "primitive_costs": request.primitive_costs,
                "assumptions": request.assumptions,
                "definitions": request.definitions,
                "optimization": {
                    "max_suggestions": request.max_plans,
                    "objective": request.objective,
                    "enabled_algorithmic_families": request.enabled_algorithmic_families,
                },
            }
        )
        computed = analyze_retained(ordinary)
        if isinstance(computed, AnalysisFailure):
            return OptimizationFailure(error=computed.error.message)
        report = _optimization_report(
            ordinary, computed, computed.work_context, analyzer=analyze_retained
        )
        if report.status == "failed":
            return OptimizationFailure(error=report.qualifications[0])
        return _bound_optimization_result(
            OptimizationSuccess(
                requested_limit=request.max_plans,
                search_status="incomplete" if report.status == "incomplete" else "complete",
                plans=report.plans,
                qualifications=report.qualifications,
            )
        )
    except Exception:
        # Direct operation failures remain typed and never expose partial candidates.
        return OptimizationFailure(error="optimization operation failed unexpectedly")
