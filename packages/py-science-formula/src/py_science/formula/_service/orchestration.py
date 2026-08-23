# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Top-level service request orchestration and dominance dispatch."""

from __future__ import annotations

from fractions import Fraction

from py_science.formula._analysis.computation import (
    _complexity_failure,
    _constant_value,
    _exact_fraction,
    _invalid,
    _scenario_literal,
    _symbol_names,
    analyze_retained,
)
from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.expressions import RelationshipOperator, Symbol, substitute
from py_science.formula.models import (
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisRequest,
    AnalysisSuccess,
    DominanceAnalysisOutcome,
    DominanceAnalysisRequest,
    OptimizationReport,
    SourceReference,
)
from py_science.formula.reasoning import ReasoningContext

from .optimization import _optimization_report
from .query_execution import _attach_queries
from .result_bounds import MAX_RESULT_BYTES, _bound_result
from .scenario_execution import scenario_results


def analyze(request: AnalysisRequest) -> AnalysisOutcome:
    """Analyze one ordinary request through service-owned enrichments."""
    result = analyze_retained(request, result_enricher=scenario_results)
    if isinstance(result, AnalysisFailure):
        return _bound_result(result)
    outcome: AnalysisOutcome = result.success
    if request.queries:
        outcome = _attach_queries(request, result)
    if isinstance(outcome, AnalysisSuccess):
        try:
            optimization = _optimization_report(
                request, result, result.work_context, analyzer=analyze_retained
            )
        except Exception:
            optimization = OptimizationReport(
                requested_limit=request.optimization.max_suggestions,
                status="failed",
                qualifications=("optimization advice failed unexpectedly",),
            )
        outcome = outcome.model_copy(update={"optimization": optimization})
    return _bound_result(outcome)


def analyze_dominance(request: DominanceAnalysisRequest) -> DominanceAnalysisOutcome:
    """Analyze retained aggregate work once, then delegate dominance policy."""
    from py_science.formula.dominance import analyze_retained as analyze_dominance_retained

    computed = analyze_retained(request.analysis_request())
    if isinstance(computed, AnalysisFailure):
        return computed
    fixed_failure = _dominance_fixed_assumption_failure(request, computed)
    if fixed_failure is not None:
        return fixed_failure
    outcome = analyze_dominance_retained(request, computed)
    if len(outcome.model_dump_json().encode("utf-8")) > MAX_RESULT_BYTES:
        return _complexity_failure("dominance result exceeds its size bound")
    return outcome


def _dominance_fixed_assumption_failure(
    request: DominanceAnalysisRequest, computed: RetainedComputation
) -> AnalysisFailure | None:
    """Reject exact fixed values that contradict checked global reasoning facts."""
    try:
        reasoning = ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            computed.knowledge.definitions,
            computed.knowledge.assumptions,
        )
    except Exception:
        # Dominance policy will return qualified abstention for unavailable
        # supplemental reasoning; do not turn that into a confident rejection.
        return None
    fixed_expressions = {name: _scenario_literal(raw) for name, raw in request.fixed.items()}
    for name, raw in request.fixed.items():
        value = _exact_fraction(raw)
        fact = reasoning.facts.get(name)
        contradicts_fact = fact is not None and (
            (fact.integer and value.denominator != 1)
            or (
                fact.lower is not None
                and (value < fact.lower or (value == fact.lower and fact.lower_strict))
            )
            or (
                fact.upper is not None
                and (value > fact.upper or (value == fact.upper and fact.upper_strict))
            )
        )
        try:
            resolved = substitute(reasoning.apply(Symbol(name)), fixed_expressions, max_nodes=4_096)
        except Exception:
            resolved = Symbol(name)
        replacement_value = _constant_value(resolved)
        if contradicts_fact or (replacement_value is not None and replacement_value != value):
            return _invalid(
                f"fixed substitution contradicts assumptions for {name}",
                source=SourceReference(path=f"fixed.{name}"),
            )
    for assumption in computed.knowledge.assumptions:
        try:
            left = _constant_value(
                substitute(
                    reasoning.apply(assumption.value.left),
                    fixed_expressions,
                    max_nodes=4_096,
                )
            )
            right = _constant_value(
                substitute(
                    reasoning.apply(assumption.value.right),
                    fixed_expressions,
                    max_nodes=4_096,
                )
            )
        except Exception:
            continue
        if (
            left is None
            or right is None
            or _fixed_relationship_holds(assumption.value.operator, left, right)
        ):
            continue
        relevant = sorted(
            (_symbol_names(assumption.value.left) | _symbol_names(assumption.value.right))
            & request.fixed.keys()
        )
        name = relevant[0] if relevant else next(iter(request.fixed))
        return _invalid(
            f"fixed substitution contradicts assumptions for {name}",
            source=SourceReference(path=f"fixed.{name}"),
        )
    return None


def _fixed_relationship_holds(
    operator: RelationshipOperator, left: Fraction, right: Fraction
) -> bool:
    if operator is RelationshipOperator.EQUAL:
        return left == right
    if operator is RelationshipOperator.LESS:
        return left < right
    if operator is RelationshipOperator.LESS_EQUAL:
        return left <= right
    if operator is RelationshipOperator.GREATER:
        return left > right
    return left >= right
