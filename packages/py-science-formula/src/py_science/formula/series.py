# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false
"""Explicit, bounded geometric-linear series rules; never calls SymPy summation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy
from py_science.formula.analyzer import count_operations
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
)
from py_science.formula.models import (
    ClosedFormEvidence,
    DerivedCandidate,
    Interpretation,
    OperationCounts,
    QueryAnswer,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import _to_query_sympy, render

MAX_NODES = 4096


@dataclass(frozen=True, slots=True)
class SeriesRule:
    candidate: Expression
    verification: str
    conditions: tuple[str, ...]
    uses: tuple[Any, ...]


def derive_closed_form(expression: Expression, reasoning: ReasoningContext | None) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound")
    sums = _sums(expression)
    if not sums:
        return _unresolved("query family is unsupported")
    if len(sums) > 8:
        return _unresolved("query family is unsupported")
    if any(_has_nested_sum(item.body) for item in sums):
        return _unresolved("nested sums are unsupported")
    if not _supported_shell(expression):
        return _unresolved("query family is unsupported")
    rules: list[SeriesRule] = []
    for item in sums:
        rule_or_answer = _derive_sum(item, reasoning)
        if isinstance(rule_or_answer, QueryAnswer):
            return rule_or_answer
        rules.append(rule_or_answer)
    candidate = expression
    for item, rule in zip(sums, rules, strict=True):
        candidate = _replace(candidate, item, rule.candidate)
    if expression_node_count(candidate) > MAX_NODES:
        return _unresolved("query derived expression exceeds its bound")
    try:
        interpretation = render(candidate)
    except Exception:
        return _unresolved("query candidate cannot be rendered")
    if max(len(interpretation.sympy), len(interpretation.latex)) > 4096:
        return _unresolved("query candidate rendering exceeds its bound")
    tally = count_operations(candidate)
    conditions = tuple(dict.fromkeys(condition for rule in rules for condition in rule.conditions))
    uses = _unique(tuple(use for rule in rules for use in rule.uses))
    statement = f"{render(expression).sympy} = {interpretation.sympy}"
    verification = (
        "infinite_partial_sum"
        if any(rule.verification == "infinite_partial_sum" for rule in rules)
        else "finite_antidifference"
    )
    return QueryAnswer(
        conclusion="proved_under_assumptions" if uses or conditions else "proved",
        conditions=conditions,
        assumptions_used=uses,
        evidence=ClosedFormEvidence(verification=verification, statement=statement),
        derived_candidates=(
            DerivedCandidate(
                interpretation=Interpretation(
                    normalized_sympy=interpretation.sympy, normalized_latex=interpretation.latex
                ),
                operation_counts=OperationCounts(
                    additions=tally.additions,
                    subtractions=tally.subtractions,
                    multiplications=tally.multiplications,
                    divisions=tally.divisions,
                    powers=tally.powers,
                ),
            ),
        ),
    )


def _derive_sum(item: Sum, reasoning: ReasoningContext) -> SeriesRule | QueryAnswer:
    if (
        _contains_forbidden(item.body)
        or _contains_index(item.lower, item.index)
        or _contains_index(item.upper, item.index)
    ):
        return _unresolved("query family is unsupported")
    lower, upper, body = (
        reasoning.apply(item.lower),
        reasoning.apply(item.upper),
        reasoning.apply(item.body),
    )
    if not reasoning.proves_integral(lower) or (
        not isinstance(upper, InfinityLiteral) and not reasoning.proves_integral(upper)
    ):
        return _unresolved("series bounds are not proved integral")
    parsed = _linear_geometric(body, item.index)
    if parsed is None:
        return _unresolved("query family is unsupported")
    if not isinstance(upper, InfinityLiteral) and not reasoning.proves_ordered(lower, upper):
        if reasoning.proves_strictly_ordered(upper, lower):
            return SeriesRule(
                IntegerLiteral(0),
                "finite_antidifference",
                (f"{render(lower).sympy} > {render(upper).sympy}: empty range",),
                (),
            )
        return _unresolved("series bounds are not proved ordered")
    a, b, r = parsed
    rho = sympy.Symbol("_series_ratio")
    try:
        a_value, b_value, r_value = _to_query_sympy(a), _to_query_sympy(b), _to_query_sympy(r)
        m_value = _to_query_sympy(lower)
        if isinstance(upper, InfinityLiteral):
            if upper.sign < 0:
                return _unresolved("query family is unsupported")
            converges, uses = reasoning.proves_abs_less_one_expression(r)
            if not converges:
                divergent, divergence_uses = reasoning.proves_abs_at_least_one(r)
                nonzero, nonzero_uses = reasoning.prove_nonzero(a if not _zero(a) else b)
                if divergent and nonzero:
                    return QueryAnswer(
                        conclusion="inapplicable",
                        conditions=("Abs(r) >= 1: the nonzero geometric-linear series diverges",),
                        assumptions_used=_unique((*divergence_uses, *nonzero_uses)),
                    )
                return _unresolved(
                    "series convergence is not proved", reasoning.relevant_unsupported(_names(item))
                )
            g = rho**m_value / (1 - rho)
            candidate_value = sympy.cancel(
                (a_value * rho * sympy.diff(g, rho) + b_value * g).subs(rho, r_value)
            )
            verification = "infinite_partial_sum"
            ratio_text = render(r).sympy
            conditions = (f"Abs({ratio_text}) < 1", f"{ratio_text} != 1")
        else:
            n_value = _to_query_sympy(upper)
            one, one_uses = reasoning.prove_equal_one(r)
            if one:
                candidate_value = sympy.cancel(
                    a_value * (n_value * (n_value + 1) - (m_value - 1) * m_value) / 2
                    + b_value * (n_value - m_value + 1)
                )
                uses = one_uses
                conditions = (f"{render(r).sympy} = 1",)
            else:
                nonzero, uses = reasoning.prove_nonzero(
                    BinaryExpression(BinaryOperator.SUBTRACT, r, IntegerLiteral(1))
                )
                nonzero = nonzero or _literal_not_one(r)
                if not nonzero:
                    return _unresolved(
                        "series ratio is neither proved equal to one nor different from one"
                    )
                g = (rho**m_value - rho ** (n_value + 1)) / (1 - rho)
                candidate_value = sympy.cancel(
                    (a_value * rho * sympy.diff(g, rho) + b_value * g).subs(rho, r_value)
                )
                conditions = (f"{render(r).sympy} != 1",)
            verification = "finite_antidifference"
        source = str(candidate_value)
        # The restricted parser deliberately has no unary-minus production.
        if source.startswith("(-"):
            source = "(0-" + source[2:]
        parsed_candidate = parse_expression(source)
        if (
            isinstance(parsed_candidate, (ParseFailure, tuple))
            or expression_node_count(parsed_candidate) > MAX_NODES
        ):
            return _unresolved("query derived expression exceeds its bound")
        # The formula above is constructed from G and r*dG/dr; cancellation is family-checked.
        return SeriesRule(parsed_candidate, verification, conditions, uses)
    except Exception:
        return _unresolved("query series construction exceeds its bound")


def _linear_geometric(
    value: Expression, index: str
) -> tuple[Expression, Expression, Expression] | None:
    powers = [
        node
        for node in _walk(value)
        if isinstance(node, BinaryExpression)
        and node.operator is BinaryOperator.POWER
        and isinstance(node.right, Symbol)
        and node.right.name == index
    ]
    if len(powers) != 1:
        return None
    power = powers[0]
    if _contains_index(power.left, index):
        return None
    try:
        k = sympy.Symbol(index)
        quotient = sympy.cancel(_to_query_sympy(value) / _to_query_sympy(power.left) ** k)
        poly = sympy.Poly(quotient, k)
        if poly.degree() > 1 or any(
            k in coefficient.free_symbols for coefficient in poly.all_coeffs()
        ):
            return None
        a = poly.coeff_monomial(k)
        b = poly.coeff_monomial(1)
        parsed_a, parsed_b = parse_expression(str(a)), parse_expression(str(b))
        if isinstance(parsed_a, (ParseFailure, tuple)) or isinstance(
            parsed_b, (ParseFailure, tuple)
        ):
            return None
        return parsed_a, parsed_b, power.left
    except Exception:
        return None


def _sums(value: Expression) -> list[Sum]:
    return [node for node in _walk(value) if isinstance(node, Sum)]


def _walk(value: Expression):
    yield value
    for child in expression_children(value):
        yield from _walk(child)


def _has_nested_sum(value: Expression) -> bool:
    return any(isinstance(node, Sum) for node in _walk(value))


def _contains_forbidden(value: Expression) -> bool:
    return any(
        isinstance(node, (Call, IndexedValue, Sum, InfinityLiteral)) for node in _walk(value)
    )


def _contains_index(value: Expression, index: str) -> bool:
    return any(isinstance(node, Symbol) and node.name == index for node in _walk(value))


def _supported_shell(value: Expression) -> bool:
    if isinstance(value, Sum):
        return not isinstance(value.upper, InfinityLiteral) or value.upper.sign > 0
    if isinstance(value, (Call, IndexedValue, InfinityLiteral)):
        return False
    return all(_supported_shell(child) for child in expression_children(value))


def _replace(value: Expression, old: Sum, new: Expression) -> Expression:
    if value == old:
        return new
    if isinstance(value, BinaryExpression):
        return BinaryExpression(
            value.operator,
            _replace(value.left, old, new),
            _replace(value.right, old, new),
        )
    return value


def _zero(value: Expression) -> bool:
    return (isinstance(value, IntegerLiteral) and value.value == 0) or (
        isinstance(value, RationalLiteral) and value.numerator == 0
    )


def _literal_not_one(value: Expression) -> bool:
    return (isinstance(value, IntegerLiteral) and value.value != 1) or (
        isinstance(value, RationalLiteral) and value.numerator != value.positive_denominator
    )


def _names(value: Expression) -> set[str]:
    return {node.name for node in _walk(value) if isinstance(node, Symbol)}


def _unique(values: tuple[Any, ...]) -> tuple[Any, ...]:
    seen: set[tuple[str, str]] = set()
    result = []
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _unresolved(blocker: str, unsupported: tuple[str, ...] = ()) -> QueryAnswer:
    return QueryAnswer(
        conclusion="unresolved", blockers=(blocker,), relevant_unsupported_assumptions=unsupported
    )
