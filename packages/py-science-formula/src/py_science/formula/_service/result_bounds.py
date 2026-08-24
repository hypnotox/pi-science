# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Service-owned result byte bounds."""

from py_science.formula._analysis.computation import (
    MAX_OPTIMIZATION_BYTES,
    MAX_RESULT_BYTES,
    _complexity_failure,
)
from py_science.formula.contracts.goals import OptimizationResult
from py_science.formula.models import AnalysisOutcome, AnalysisSuccess


def _bound_result(outcome: AnalysisOutcome) -> AnalysisOutcome:
    if (
        isinstance(outcome, AnalysisSuccess)
        and len(outcome.model_dump_json().encode("utf-8")) > MAX_RESULT_BYTES
    ):
        return _complexity_failure("analysis result exceeds its size bound")
    return outcome


def _bound_optimization_result(outcome: OptimizationResult) -> OptimizationResult:
    measured = len(outcome.model_dump_json().encode("utf-8"))
    if measured <= MAX_OPTIMIZATION_BYTES:
        return outcome
    qualification = (
        "optimization result bytes budget exhausted "
        f"(measured {measured}, configured {MAX_OPTIMIZATION_BYTES})"
    )
    combined = tuple(dict.fromkeys((*outcome.projection_qualifications, qualification)))
    if len(combined) > 128:
        combined = (*combined[:127], qualification)
    qualification_populations = (
        (combined, (qualification,)) if combined != (qualification,) else (combined,)
    )
    for qualifications in qualification_populations:
        for retained in range(len(outcome.plans), -1, -1):
            bounded = outcome.model_copy(
                update={
                    "plans": outcome.plans[:retained],
                    "projection_status": "truncated",
                    "projection_qualifications": qualifications,
                }
            )
            if len(bounded.model_dump_json().encode("utf-8")) <= MAX_OPTIMIZATION_BYTES:
                return bounded
    raise ValueError("optimization result bound cannot contain its exhaustion diagnostic")
