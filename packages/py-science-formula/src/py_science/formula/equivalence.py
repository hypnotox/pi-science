# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Bounded expression-to-expression equivalence proof seam."""

from __future__ import annotations

from itertools import product
from typing import Any

import sympy
from py_science.formula.exact_values import ExactRational, render_exact
from py_science.formula.expressions import Expression, IntegerLiteral, Symbol, expression_children
from py_science.formula.models import CounterexampleEvidence, IdentityEvidence, QueryAnswer
from py_science.formula.query_diagnostics import RATIONAL_FAILURE_REASONS, QueryDiagnostic
from py_science.formula.reasoning import ReasoningContext, collect_denominators
from py_science.formula.sympy_backend import (
    RationalMeasureFailure,
    bounded_rational_difference,
    rational_ir_measure,
    render,
)

MAX_COUNTEREXAMPLE_STEPS = 256


def equivalence_answer(
    expression: Expression, comparison: Expression, reasoning: ReasoningContext | None
) -> QueryAnswer:
    """Compare two already-parsed operands under bounded rational reasoning."""
    if reasoning is None:
        return _unresolved_with("query reasoning exceeds its bound")
    original_symbols = _symbol_names(expression) | _symbol_names(comparison)
    try:
        left, right = reasoning.apply(expression), reasoning.apply(comparison)
    except Exception:
        return _unresolved_with("query reasoning exceeds its bound")
    relevant_symbols = _symbol_names(left) | _symbol_names(right) | original_symbols
    unsupported = reasoning.relevant_unsupported(relevant_symbols)
    operand_failure = _rational_diagnostic(
        expression, "equivalence operand"
    ) or _rational_diagnostic(comparison, "equivalence operand")
    if operand_failure is not None:
        return _unresolved_with(operand_failure.render())
    expansion_failure = _rational_diagnostic(left, "equivalence expansion") or _rational_diagnostic(
        right, "equivalence expansion"
    )
    if expansion_failure is not None:
        return _unresolved_with(expansion_failure.render())
    original_denominators = (*collect_denominators(left), *collect_denominators(right))
    normalized = bounded_rational_difference(left, right)
    if normalized is None:
        return _unresolved_with("query rational normalization exceeds its bound", unsupported)
    conditions: list[str] = []
    obligation_uses = []
    for denominator in original_denominators:
        denominator_normalized = bounded_rational_difference(denominator, IntegerLiteral(0))
        if denominator_normalized is None:
            return _unresolved_with("query denominator exceeds its bound", unsupported)
        if denominator_normalized.numerator == 0:
            return _unresolved_with("query denominator is identically zero", unsupported)
        try:
            statement = f"{render(denominator).sympy} != 0"
        except Exception:
            return _unresolved_with("query denominator cannot be rendered", unsupported)
        if len(statement) > 4096:
            return _unresolved_with("query denominator rendering exceeds its bound", unsupported)
        if statement not in conditions:
            conditions.append(statement)
        proved, uses = reasoning.prove_nonzero(denominator)
        if proved:
            obligation_uses.extend(uses)
    used = _unique_uses(
        (
            *reasoning.relevant_uses(relevant_symbols, include_facts=bool(original_denominators)),
            *obligation_uses,
        )
    )
    if len(used) > 128:
        return _unresolved_with("query assumption provenance exceeds its bound", unsupported)
    if normalized.numerator == 0:
        return QueryAnswer(
            conclusion="proved_under_assumptions" if used or conditions else "proved",
            conditions=tuple(conditions),
            assumptions_used=used,
            relevant_unsupported_assumptions=unsupported,
            evidence=IdentityEvidence(statement="normalized difference is zero"),
        )
    if (
        not normalized.left.free_symbols
        and not normalized.right.free_symbols
        and normalized.numerator.is_number
    ):
        if not normalized.left.is_Rational or not normalized.right.is_Rational:
            return _unresolved_with("query evidence is not a finite exact value", unsupported)
        target_rendered, comparison_rendered = str(normalized.left), str(normalized.right)
        if max(len(target_rendered), len(comparison_rendered)) > 4096:
            return _unresolved_with("query evidence rendering exceeds its bound", unsupported)
        return QueryAnswer(
            conclusion="disproved",
            conditions=tuple(conditions),
            assumptions_used=used,
            relevant_unsupported_assumptions=unsupported,
            evidence=CounterexampleEvidence(
                substitutions={}, target_value=target_rendered, comparison_value=comparison_rendered
            ),
        )
    candidates = (
        sympy.Rational(0),
        sympy.Rational(1),
        sympy.Rational(-1),
        sympy.Rational(2),
        sympy.Rational(-2),
        sympy.Rational(1, 2),
        sympy.Rational(-1, 2),
    )
    for steps, items in enumerate(product(candidates, repeat=len(normalized.symbols)), 1):
        if steps > MAX_COUNTEREXAMPLE_STEPS:
            break
        values = dict(zip(normalized.symbols, items, strict=True))
        try:
            if (
                not reasoning.assignment_valid(values)
                or any(
                    _sympy_denominator(denominator).subs(values) == 0
                    for denominator in original_denominators
                )
                or normalized.denominator.subs(values) == 0
                or normalized.numerator.subs(values) == 0
            ):
                continue
            target_value, comparison_value = (
                normalized.left.subs(values),
                normalized.right.subs(values),
            )
            if (
                target_value.free_symbols
                or comparison_value.free_symbols
                or not target_value.is_Rational
                or not comparison_value.is_Rational
            ):
                continue
            target_rendered, comparison_rendered = str(target_value), str(comparison_value)
            if max(len(target_rendered), len(comparison_rendered)) > 4096:
                return _unresolved_with("query evidence rendering exceeds its bound", unsupported)
            candidate_uses = reasoning.relevant_uses(relevant_symbols, include_facts=True)
            if len(candidate_uses) > 128:
                return _unresolved_with(
                    "query assumption provenance exceeds its bound", unsupported
                )
            return QueryAnswer(
                conclusion="disproved",
                conditions=tuple(conditions),
                assumptions_used=candidate_uses,
                relevant_unsupported_assumptions=unsupported,
                evidence=CounterexampleEvidence(
                    substitutions={
                        str(key): _canonical_exact(value) for key, value in values.items()
                    },
                    target_value=target_rendered,
                    comparison_value=comparison_rendered,
                ),
            )
        except Exception:
            continue
    return _unresolved_with(
        "no bounded counterexample satisfies the supported assumptions", unsupported
    )


def _rational_diagnostic(expression: Expression, subject: str) -> QueryDiagnostic | None:
    measurement = rational_ir_measure(expression)
    return (
        None
        if not isinstance(measurement, RationalMeasureFailure)
        else QueryDiagnostic(
            subject,
            RATIONAL_FAILURE_REASONS[measurement.kind],
            measurement.observed,
            measurement.configured,
            "use bounded rational operands",
        )
    )


def _symbol_names(expression: Expression) -> set[str]:
    names = {expression.name} if isinstance(expression, Symbol) else set()
    for child in expression_children(expression):
        names |= _symbol_names(child)
    return names


def _sympy_denominator(expression: Expression) -> Any:
    normalized = bounded_rational_difference(expression, IntegerLiteral(0))
    if normalized is None:
        raise ValueError("unsupported denominator")
    return normalized.left


def _canonical_exact(value: Any) -> str:
    return render_exact(ExactRational(int(value.p), int(value.q)))


def _unique_uses(values: tuple[Any, ...]) -> tuple[Any, ...]:
    seen: set[tuple[str, str]] = set()
    result = []
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _unresolved_with(blocker: str, unsupported: tuple[str, ...] = ()) -> QueryAnswer:
    return QueryAnswer(
        conclusion="unresolved", blockers=(blocker,), relevant_unsupported_assumptions=unsupported
    )
