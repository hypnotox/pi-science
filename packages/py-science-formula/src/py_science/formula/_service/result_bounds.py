# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Service-owned result byte bounds."""

from py_science.formula._analysis.computation import (
    MAX_COMBINED_RESULT_BYTES,
    MAX_OPTIMIZATION_BYTES,
    MAX_RESULT_BYTES,
    _complexity_failure,
)
from py_science.formula.models import AnalysisOutcome, AnalysisSuccess, OptimizationSuccess


def _bound_result(outcome: AnalysisOutcome) -> AnalysisOutcome:
    if isinstance(outcome, AnalysisSuccess):
        advice = outcome.optimization
        # Preserve the pre-advice success population exactly: the optional
        # internal field itself must not consume the historical base allowance.
        base_bytes = len(outcome.model_dump_json(exclude={"optimization"}).encode("utf-8"))
        if base_bytes > MAX_RESULT_BYTES:
            return _complexity_failure("analysis result exceeds its base size bound")
        advice_contribution = len(outcome.model_dump_json().encode("utf-8")) - base_bytes
        if advice_contribution > MAX_OPTIMIZATION_BYTES:
            qualification = (
                "optimization advice bytes budget exhausted "
                f"(measured {advice_contribution}, configured {MAX_OPTIMIZATION_BYTES})"
            )
            for retained in range(len(advice.plans), -1, -1):
                bounded_advice = advice.model_copy(
                    update={
                        "suggestions": advice.suggestions[:retained],
                        "plans": advice.plans[:retained],
                        "projection_status": "truncated",
                        "projection_qualifications": tuple(
                            dict.fromkeys((*advice.projection_qualifications, qualification))
                        ),
                    }
                )
                bounded_outcome = outcome.model_copy(update={"optimization": bounded_advice})
                bounded_contribution = (
                    len(bounded_outcome.model_dump_json().encode("utf-8")) - base_bytes
                )
                if bounded_contribution <= MAX_OPTIMIZATION_BYTES:
                    outcome = bounded_outcome
                    break
            else:
                # A pathological pre-existing qualification can consume the entire
                # optimization allowance. Preserve the valid base analysis and both
                # diagnostic classes with bounded summaries rather than promoting a
                # passive presentation limit to a whole-analysis failure.
                search_qualifications = advice.qualifications
                if advice.status == "incomplete":
                    search_qualifications = (
                        "optimization search qualifications truncated by output projection",
                    )
                bounded_advice = advice.model_copy(
                    update={
                        "suggestions": (),
                        "plans": (),
                        "qualifications": search_qualifications,
                        "projection_status": "truncated",
                        "projection_qualifications": (
                            "optimization advice bytes budget exhausted",
                        ),
                    }
                )
                outcome = outcome.model_copy(update={"optimization": bounded_advice})
        if len(outcome.model_dump_json().encode("utf-8")) > MAX_COMBINED_RESULT_BYTES:
            return _complexity_failure("analysis result exceeds its combined size bound")
    return outcome


def _bound_optimization_result(outcome: OptimizationSuccess) -> OptimizationSuccess:
    measured = len(outcome.model_dump_json().encode("utf-8"))
    if measured <= MAX_OPTIMIZATION_BYTES:
        return outcome
    qualification = (
        "optimization result bytes budget exhausted "
        f"(measured {measured}, configured {MAX_OPTIMIZATION_BYTES})"
    )
    for retained in range(len(outcome.plans), -1, -1):
        bounded = outcome.model_copy(
            update={
                "projection_status": "truncated",
                "plans": outcome.plans[:retained],
                "projection_qualifications": (qualification,),
            }
        )
        if len(bounded.model_dump_json().encode("utf-8")) <= MAX_OPTIMIZATION_BYTES:
            return bounded
    raise ValueError("optimization result bound cannot contain its exhaustion diagnostic")
