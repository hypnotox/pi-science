# ruff: noqa: E501
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportAssignmentType=false, reportUnnecessaryComparison=false, reportArgumentType=false
"""Bounded, exact asymptotic expansions; generic SymPy series/limit is forbidden."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import sympy
from py_science.formula.exact_values import parse_exact_scalar
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    IntegerLiteral,
    RationalLiteral,
    Symbol,
)
from py_science.formula.models import (
    AsymptoticEvidence,
    AsymptoticQuery,
    AsymptoticRemainder,
    QueryAnswer,
)
from py_science.formula.reasoning import ReasoningContext, collect_denominators
from py_science.formula.sympy_backend import bounded_rational_difference

MAX_INTERMEDIATE_NODES = 4096
MAX_COEFFICIENT_BITS = 1024


def asymptotic_answer(
    expression: Expression, query: AsymptoticQuery, reasoning: ReasoningContext | None
) -> QueryAnswer:
    """Expand only a preflighted univariate rational form in its declared local parameter."""
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound")
    try:
        applied = reasoning.apply(expression)
    except Exception:
        return _unresolved("query reasoning exceeds its bound")
    exponential = _exponential_linear(applied, query)
    if exponential is not None:
        uses = reasoning.application_uses((query.variable,))
        return QueryAnswer(
            conclusion="proved_under_assumptions" if uses else "proved",
            conditions=(f"{query.variable} -> {query.point}", f"base {exponential[0]} > 0"),
            assumptions_used=uses,
            evidence=AsymptoticEvidence(
                statement=f"{exponential[1]} = {exponential[2]} as x -> {query.point} (exact exhausted expansion)",
                remainder=None,
            ),
        )
    normalized = bounded_rational_difference(applied, IntegerLiteral(0))
    if normalized is None:
        return _unresolved("query family is unsupported")
    variable = sympy.Symbol(query.variable)
    if set(normalized.symbols) - {variable}:
        return _unresolved("asymptotic expansion is not univariate")
    try:
        numerator = sympy.Poly(normalized.left.as_numer_denom()[0], variable)
        denominator = sympy.Poly(normalized.left.as_numer_denom()[1], variable)
    except Exception:
        return _unresolved("query family is unsupported")
    if denominator.is_zero:
        return _unresolved("query denominator is identically zero")
    if max(numerator.degree(), denominator.degree()) > 8:
        return _unresolved("query family is unsupported")
    point = str(query.point)
    if point in {"oo", "-oo"}:
        sign = 1 if point == "oo" else -1
        local = "1/x" if sign > 0 else "-1/x"
        top = _reversed(numerator, sign)
        bottom = _reversed(denominator, sign)
        shift = int(denominator.degree()) - int(numerator.degree())
        approach = f"x -> {point}"
    else:
        exact = parse_exact_scalar(point)
        if exact is None:
            return _unresolved("asymptotic point is invalid")
        center = sympy.Rational(exact.numerator, exact.denominator)
        local = f"x - {center}"
        top = _shifted(numerator, center)
        bottom = _shifted(denominator, center)
        top_order = _valuation(top)
        bottom_order = _valuation(bottom)
        if bottom_order is None:
            return _unresolved("query denominator is identically zero")
        shift = (top_order or 0) - bottom_order
        top = top[(top_order or 0) :]
        bottom = bottom[bottom_order:]
        approach = f"x -> {center} ({query.direction})"
    if not bottom or bottom[0] == 0:
        return _unresolved("asymptotic local denominator is unsupported")
    count = query.order - shift
    if count <= 0:
        coefficients: list[Any] = []
    else:
        computed = _truncated_divide(top, bottom, int(count))
        if computed is None:
            return _unresolved("asymptotic intermediate exceeds its bound")
        coefficients = computed
    if not _verify_truncation(top, bottom, coefficients):
        return _unresolved("asymptotic remainder verification failed")
    terms = _render_terms(coefficients, shift, "t")
    denominator_conditions: list[str] = []
    for denominator_expression in collect_denominators(expression):
        obligation = bounded_rational_difference(denominator_expression, IntegerLiteral(0))
        if obligation is None:
            return _unresolved("original denominator exceeds its bound")
        condition = f"{sympy.sstr(obligation.left)} != 0"
        if condition not in denominator_conditions:
            denominator_conditions.append(condition)
    remainder = AsymptoticRemainder(
        local_parameter=local, exponent=query.order, normalized_big_o=f"O(t**{query.order})"
    )
    statement = (
        f"{sympy.sstr(normalized.left)} = {terms} + O(t**{query.order}) as {approach}, t = {local}"
    )
    if len(statement) > 4096 or any(len(sympy.sstr(value)) > 4096 for value in coefficients):
        return _unresolved("query result rendering exceeds its bound")
    return QueryAnswer(
        conclusion="proved_under_assumptions"
        if reasoning.application_uses(tuple(sorted(str(item) for item in normalized.symbols)))
        else "proved",
        assumptions_used=reasoning.application_uses(
            tuple(sorted(str(item) for item in normalized.symbols))
        ),
        conditions=(approach, *denominator_conditions),
        evidence=AsymptoticEvidence(statement=statement, remainder=remainder),
    )


def _exponential_linear(
    expression: Expression, query: AsymptoticQuery
) -> tuple[str, str, str] | None:
    """Recognize an explicit finite same-base (a*x+b)*r**x decomposition only."""
    if str(query.point) not in {"oo", "-oo"}:
        return None
    terms = _add_terms(expression)
    collected: dict[int, Fraction] = {}
    base: Fraction | None = None
    for term in terms:
        factors = _multiply_factors(term)
        powers = [item for item in factors if _power_base(item, query.variable) is not None]
        if len(powers) != 1:
            return None
        current_base = _power_base(powers[0], query.variable)
        if current_base is None or current_base <= 0:
            return None
        if base is None:
            base = current_base
        elif base != current_base:
            return None
        remaining = [item for item in factors if item is not powers[0]]
        linear = _linear_product(remaining, query.variable)
        if linear is None:
            return None
        slope, intercept = linear
        if slope:
            collected[1] = collected.get(1, Fraction(0)) + slope
        if intercept:
            collected[0] = collected.get(0, Fraction(0)) + intercept
    if base is None:
        return None
    collected = {degree: value for degree, value in collected.items() if value}
    if not collected or len(collected) > query.order:
        return None
    base_text: str = str(sympy.sstr(sympy.Rational(base.numerator, base.denominator)))
    pieces = []
    for degree in sorted(collected, reverse=True):
        coefficient: str = str(
            sympy.sstr(sympy.Rational(collected[degree].numerator, collected[degree].denominator))
        )
        polynomial = coefficient if degree == 0 else f"({coefficient})*x"
        pieces.append(f"({polynomial})*({base_text})**x")
    source = _expression_text(expression)
    result = " + ".join(pieces)
    if max(len(source), len(result)) > 4096:
        return None
    return base_text, source, result


def _add_terms(value: Expression) -> list[Expression]:
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.ADD:
        return [*_add_terms(value.left), *_add_terms(value.right)]
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.SUBTRACT:
        return [*_add_terms(value.left), *_negated_terms(value.right)]
    return [value]


def _negated_terms(value: Expression) -> list[Expression]:
    return [BinaryExpression(BinaryOperator.MULTIPLY, IntegerLiteral(-1), value)]


def _multiply_factors(value: Expression) -> list[Expression]:
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.MULTIPLY:
        return [*_multiply_factors(value.left), *_multiply_factors(value.right)]
    return [value]


def _power_base(value: Expression, variable: str) -> Fraction | None:
    if not (
        isinstance(value, BinaryExpression)
        and value.operator is BinaryOperator.POWER
        and isinstance(value.right, Symbol)
        and value.right.name == variable
    ):
        return None
    return _constant(value.left)


def _constant(value: Expression) -> Fraction | None:
    if isinstance(value, IntegerLiteral):
        return Fraction(value.value)
    if isinstance(value, RationalLiteral):
        return Fraction(value.numerator, value.positive_denominator)
    return None


def _linear_product(factors: list[Expression], variable: str) -> tuple[Fraction, Fraction] | None:
    slope, intercept = Fraction(0), Fraction(1)
    for factor in factors:
        linear = _linear(factor, variable)
        if linear is None:
            return None
        next_slope, next_intercept = linear
        if slope and next_slope:
            return None
        slope, intercept = (
            slope * next_intercept + intercept * next_slope,
            intercept * next_intercept,
        )
    return slope, intercept


def _linear(value: Expression, variable: str) -> tuple[Fraction, Fraction] | None:
    constant = _constant(value)
    if constant is not None:
        return Fraction(0), constant
    if isinstance(value, Symbol) and value.name == variable:
        return Fraction(1), Fraction(0)
    if not isinstance(value, BinaryExpression):
        return None
    left, right = _linear(value.left, variable), _linear(value.right, variable)
    if left is None or right is None:
        return None
    if value.operator is BinaryOperator.ADD:
        return left[0] + right[0], left[1] + right[1]
    if value.operator is BinaryOperator.SUBTRACT:
        return left[0] - right[0], left[1] - right[1]
    if value.operator is BinaryOperator.MULTIPLY:
        if left[0] and right[0]:
            return None
        return left[0] * right[1] + left[1] * right[0], left[1] * right[1]
    return None


def _expression_text(value: Expression) -> str:
    # This renderer is deliberately restricted to the accepted decomposition.
    if isinstance(value, IntegerLiteral):
        return str(value.value)
    if isinstance(value, RationalLiteral):
        return f"{value.numerator}/{value.positive_denominator}"
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, BinaryExpression):
        op = {
            BinaryOperator.ADD: "+",
            BinaryOperator.SUBTRACT: "-",
            BinaryOperator.MULTIPLY: "*",
            BinaryOperator.POWER: "**",
        }.get(value.operator)
        if op is not None:
            return f"({_expression_text(value.left)} {op} {_expression_text(value.right)})"
    return "accepted exponential expression"


def _reversed(poly: Any, sign: int) -> list[Any]:
    degree = poly.degree()
    return [poly.nth(degree - index) * (sign ** (degree - index)) for index in range(degree + 1)]


def _shifted(poly: Any, center: Any) -> list[Any]:
    """Explicit binomial translation P(c+t), avoiding generic expansion."""
    degree = poly.degree()
    result = [sympy.Rational(0) for _ in range(degree + 1)]
    for power in range(degree + 1):
        coefficient = poly.nth(power)
        for local_power in range(power + 1):
            result[local_power] += (
                coefficient * sympy.binomial(power, local_power) * center ** (power - local_power)
            )
    return result


def _valuation(values: list[Any]) -> int | None:
    return next((index for index, value in enumerate(values) if value != 0), None)


def _truncated_divide(top: list[Any], bottom: list[Any], count: int) -> list[Any] | None:
    quotient: list[Any] = []
    for index in range(count):
        value = top[index] if index < len(top) else sympy.Rational(0)
        value -= sum(
            bottom[offset] * quotient[index - offset]
            for offset in range(1, min(index, len(bottom) - 1) + 1)
        )
        coefficient = value / bottom[0]
        if not _bounded(coefficient):
            return None
        quotient.append(coefficient)
    return quotient


def _verify_truncation(top: list[Any], bottom: list[Any], quotient: list[Any]) -> bool:
    """The recurrence is checked independently as the exact truncated rational identity."""
    try:
        for index in range(len(quotient)):
            product = sum(
                bottom[offset] * quotient[index - offset]
                for offset in range(min(index, len(bottom) - 1) + 1)
            )
            if sympy.cancel((top[index] if index < len(top) else 0) - product) != 0:
                return False
        return True
    except Exception:
        return False


def _bounded(value: Any) -> bool:
    try:
        top, bottom = sympy.fraction(value)
        return (
            top.is_Integer
            and bottom.is_Integer
            and max(abs(int(top)).bit_length(), abs(int(bottom)).bit_length())
            <= MAX_COEFFICIENT_BITS
        )
    except Exception:
        return False


def _render_terms(coefficients: list[Any], shift: int, parameter: str) -> str:
    rendered: list[str] = []
    for index, coefficient in enumerate(coefficients):
        if coefficient == 0:
            continue
        exponent = shift + index
        value = sympy.sstr(coefficient)
        if exponent == 0:
            rendered.append(value)
        elif exponent == 1:
            rendered.append(f"({value})*{parameter}")
        else:
            rendered.append(f"({value})*{parameter}**{exponent}")
    return " + ".join(rendered) if rendered else "0"


def _unresolved(blocker: str) -> QueryAnswer:
    return QueryAnswer(conclusion="unresolved", blockers=(blocker,))
