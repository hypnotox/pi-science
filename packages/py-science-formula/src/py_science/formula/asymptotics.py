"""Policy orchestration for bounded asymptotic queries.

All SymPy translation, polynomial arithmetic, verification, and rendering live in
``sympy_backend``.  This module owns only query qualification and result shape.
"""
from __future__ import annotations

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportMissingParameterType=false
from py_science.formula.expressions import Expression, Symbol, expression_children
from py_science.formula.models import (
    AsymptoticEvidence,
    AsymptoticQuery,
    AsymptoticRemainder,
    QueryAnswer,
    RelationshipUse,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import (
    bounded_asymptotic_rational,
    bounded_exponential_decomposition,
)


def asymptotic_answer(
    expression: Expression,
    query: AsymptoticQuery,
    reasoning: ReasoningContext | None,
    *,
    original_expression: Expression | None = None,
) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound")
    try:
        applied = reasoning.apply(expression)
    except Exception:
        return _unresolved("query reasoning exceeds its bound")

    exponential = bounded_exponential_decomposition(
        applied, query.variable, str(query.point), query.order
    )
    if exponential is not None:
        # The backend has reconstructed and checked the exact submitted decomposition.
        symbols = exponential.symbols
        uses = reasoning.application_uses(symbols)
        base_uses = reasoning.exponential_base_uses(exponential.bases)
        all_uses = _unique((*uses, *base_uses))
        if not reasoning.exponential_facts_hold(exponential.bases, exponential.coefficient_symbols):
            return _unresolved("exponential coefficient or base facts are unresolved")
        return QueryAnswer(
            conclusion=(
                "proved_under_assumptions" if all_uses or exponential.conditions else "proved"
            ),
            conditions=(f"{query.variable} -> {query.point}", *exponential.conditions),
            assumptions_used=all_uses,
            relevant_unsupported_assumptions=reasoning.relevant_unsupported(set(symbols)),
            evidence=AsymptoticEvidence(
                statement=(f"{exponential.source} = {exponential.rendered} as "
                           f"{query.variable} -> {query.point} (exact exhausted expansion)"),
                remainder=None,
            ),
        )

    rational = bounded_asymptotic_rational(
        applied,
        original_expression or expression,
        query.variable,
        str(query.point),
        query.order,
        query.direction,
        frozenset(
            symbol
            for symbol in _expression_symbols(applied)
            if symbol != query.variable and reasoning.real_symbols_hold((symbol,))
        ),
    )
    if rational is None:
        return _unresolved("query family is unsupported")
    if rational.failure is not None:
        return _unresolved(rational.failure)
    uses = reasoning.application_uses(rational.symbols)
    # A denominator condition or provenance is an assumption-qualified proof.
    return QueryAnswer(
        conclusion="proved_under_assumptions" if uses or rational.conditions else "proved",
        conditions=rational.conditions,
        assumptions_used=uses,
        relevant_unsupported_assumptions=reasoning.relevant_unsupported(set(rational.symbols)),
        evidence=AsymptoticEvidence(
            statement=rational.statement,
            remainder=AsymptoticRemainder(
                local_parameter=rational.local_parameter,
                exponent=query.order,
                normalized_big_o=f"O(t**{query.order})",
            ),
        ),
    )


def _expression_symbols(expression: Expression) -> set[str]:
    if isinstance(expression, Symbol):
        return {expression.name}
    return set().union(*(_expression_symbols(child) for child in expression_children(expression)))


def _unique(values: tuple[RelationshipUse, ...]) -> tuple[RelationshipUse, ...]:
    seen: set[tuple[str, str]] = set()
    result = []
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _unresolved(blocker: str) -> QueryAnswer:
    return QueryAnswer(conclusion="unresolved", blockers=(blocker,))
