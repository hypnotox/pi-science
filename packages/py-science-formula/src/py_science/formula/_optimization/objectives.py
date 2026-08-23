# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Private optimizer owner."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from py_science.formula.expressions import (
    expression_node_count,
)
from py_science.formula.models import (
    OptimizationSuggestion,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.work import (
    AggregateWorkComparisonInput,
    compare_aggregate_work,
)

from .budgets import _OptimizationBudget
from .verifier import _Accepted


def _suggestion_order(left: OptimizationSuggestion, right: OptimizationSuggestion) -> int:
    if (left.conclusion == "proved") != (right.conclusion == "proved"):
        return -1 if left.conclusion == "proved" else 1
    try:
        left_savings = Fraction(left.objective_savings)
        right_savings = Fraction(right.objective_savings)
    except (ValueError, ZeroDivisionError):
        left_savings = right_savings = None
    if left_savings is not None and right_savings is not None and left_savings != right_savings:
        return -1 if left_savings > right_savings else 1
    left_key = (
        tuple(
            (item.target.name or "", item.occurrences[0].path, item.proposed.normalized_sympy)
            for item in left.transformations
        ),
        left.kind,
    )
    right_key = (
        tuple(
            (item.target.name or "", item.occurrences[0].path, item.proposed.normalized_sympy)
            for item in right.transformations
        ),
        right.kind,
    )
    return (left_key > right_key) - (left_key < right_key)


def _accepted_order(
    left: _Accepted,
    right: _Accepted,
    reasoning: ReasoningContext,
    budget: _OptimizationBudget,
) -> int:
    base = _suggestion_order(left.suggestion, right.suggestion)
    if (left.suggestion.conclusion == "proved") != (right.suggestion.conclusion == "proved"):
        return base
    try:
        left_exact = Fraction(left.suggestion.objective_savings)
        right_exact = Fraction(right.suggestion.objective_savings)
    except (ValueError, ZeroDivisionError):
        left_exact = right_exact = None
    if left_exact is not None and right_exact is not None:
        return base
    if (
        left.suggestion.conditions != right.suggestion.conditions
        or left.suggestion.assumptions_used != right.suggestion.assumptions_used
    ):
        return base
    budget.work(
        expression_node_count(left.savings_expression)
        + expression_node_count(right.savings_expression)
    )
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(work=left.savings_expression),
        AggregateWorkComparisonInput(work=right.savings_expression),
        reasoning,
        semantic_established=True,
    )
    if relation.conditions or relation.assumptions_used:
        return base
    if relation.status == "first_lower":
        return 1
    if relation.status == "second_lower":
        return -1
    return base


def _adjacent_ordering_relation(
    previous: _Accepted,
    current: _Accepted,
    reasoning: ReasoningContext,
    budget: _OptimizationBudget,
) -> Literal["previous_proved_superior", "deterministic_non_superiority"]:
    if (
        previous.suggestion.conclusion != current.suggestion.conclusion
        or previous.suggestion.conditions != current.suggestion.conditions
        or previous.suggestion.assumptions_used != current.suggestion.assumptions_used
    ):
        return "deterministic_non_superiority"
    try:
        previous_exact = Fraction(previous.suggestion.objective_savings)
        current_exact = Fraction(current.suggestion.objective_savings)
    except (ValueError, ZeroDivisionError):
        previous_exact = current_exact = None
    if previous_exact is not None and current_exact is not None:
        return (
            "previous_proved_superior"
            if previous_exact > current_exact
            else "deterministic_non_superiority"
        )
    budget.work(
        expression_node_count(previous.savings_expression)
        + expression_node_count(current.savings_expression)
    )
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(work=previous.savings_expression),
        AggregateWorkComparisonInput(work=current.savings_expression),
        reasoning,
        semantic_established=True,
    )
    if relation.conditions or relation.assumptions_used:
        return "deterministic_non_superiority"
    return (
        "previous_proved_superior"
        if relation.status == "second_lower"
        else "deterministic_non_superiority"
    )
