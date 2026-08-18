"""Bounded exact rational properties and limits.

Mathematical policy lives here; every SymPy transformation is confined to the
narrow, resource-checked seams in :mod:`sympy_backend`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Any

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.exact_values import ExactRational, parse_exact_scalar, render_exact
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    InfinityLiteral,
    Sum,
    Symbol,
)
from py_science.formula.models import (
    LimitEvidence,
    LimitQuery,
    PropertyCheck,
    PropertyEvidence,
    QueryAnswer,
    RelationshipUse,
)
from py_science.formula.query_diagnostics import RATIONAL_FAILURE_REASONS, QueryDiagnostic
from py_science.formula.reasoning import DomainFact, ReasoningContext, collect_denominators
from py_science.formula.sympy_backend import (
    RationalMeasureFailure,
    property_affine_coefficients,
    property_cancel,
    property_derivative,
    property_difference,
    property_factor_components,
    property_factor_roots,
    property_fraction,
    property_local_pole_coefficient,
    property_polynomial_info,
    property_render,
    property_substitute,
    property_value,
    rational_ir_measure,
)


@dataclass(frozen=True, slots=True)
class RationalShape:
    """Cancelled rational value plus the original submitted exclusions."""

    value: Any
    numerator: Any
    denominator: Any
    variable: Any
    original_denominators: tuple[Any, ...]
    original_denominator_expressions: tuple[Expression, ...]
    uses: tuple[RelationshipUse, ...]


def afmm_tail_property_answer(
    expression: Expression, check: PropertyCheck, reasoning: ReasoningContext | None
) -> QueryAnswer | None:
    """Qualify the Phase-3-verified ``Sum((k + 1) * q**k, (k, p, oo))`` family.

    This is intentionally an exact grammar for the identity's approved family,
    not a generic series recognizer.
    """
    if reasoning is None or not _is_afmm_tail(expression):
        return None
    assert isinstance(expression, Sum) and isinstance(expression.lower, Symbol)
    q = _afmm_ratio(expression.body, expression.index)
    assert q is not None
    p = expression.lower.name
    p_fact, q_fact = reasoning.facts.get(p), reasoning.facts.get(q)
    if not _afmm_conditions(p_fact, q_fact):
        return None
    assert p_fact is not None and q_fact is not None
    p_uses, q_uses = p_fact.sources, q_fact.sources
    if check.kind == "valid_domain" and check.variable == q:
        return _proved(check, "exclude 1", (f"{q} != 1",), q_uses)
    if check.kind == "singularities" and check.variable == q:
        return _proved(check, f"{q} = 1: pole of order 2; outside the active domain", (), q_uses)
    if check.kind == "sign":
        p_zero = _fact_is_zero(p_fact)
        strict = _fact_is_strictly_positive(q_fact) or p_zero
        uses = _unique((*p_uses, *q_uses))
        return _proved(
            check,
            "strictly positive" if strict else "nonnegative (strict positivity is not proved)",
            (f"0 <= {q} < 1",),
            uses,
        )
    if check.kind == "monotonicity" and check.variable == p:
        return _proved(
            check,
            "nonincreasing (integer forward difference)",
            (f"{p} >= 0",),
            _unique((*p_uses, *q_uses)),
        )
    if check.kind == "monotonicity" and check.variable == q:
        return _proved(check, "nondecreasing", (f"0 <= {q} < 1",), _unique((*p_uses, *q_uses)))
    return None


def property_answer(
    expression: Expression, check: PropertyCheck, reasoning: ReasoningContext | None
) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound", check)
    shape = _shape(
        expression,
        check.variable if check.kind != "sign" else None,
        reasoning,
        subject="properties target",
    )
    if isinstance(shape, QueryDiagnostic):
        return _unresolved(shape.render(), check)
    obligation = _parameter_denominator_obligations(shape, reasoning)
    if obligation is None:
        return _unresolved("original denominator is not proved nonzero", check)
    obligation_conditions, obligation_uses = obligation
    if check.kind == "sign" and reasoning.facts.get(str(shape.variable)) is None:
        return QueryAnswer(
            check=check,
            conclusion="inapplicable",
            blockers=("realness of the query variable is not proved",),
        )
    if check.kind == "valid_domain":
        roots = _all_roots(shape.original_denominators, shape.variable)
        if roots is None:
            return _unresolved("denominator factors are unsupported", check)
        rendered = tuple(_render(root) for root, _ in roots)
        if any(item is None for item in rendered):
            return _unresolved("denominator factors are unsupported", check)
        exclusions = tuple(item for item in rendered if item is not None)
        return _proved(
            check,
            "all real values" if not exclusions else "exclude " + ", ".join(exclusions),
            tuple(f"{check.variable} != {root}" for root in exclusions),
            _unique((*shape.uses, *obligation_uses)),
            conditions=obligation_conditions,
        )
    if check.kind == "singularities":
        roots = _roots(shape.denominator, shape.variable)
        if roots is None:
            return _unresolved("denominator factors are unsupported", check)
        if not roots:
            return _proved(
                check,
                "no singularities",
                (),
                _unique((*shape.uses, *obligation_uses)),
                conditions=obligation_conditions,
            )
        domain = reasoning.facts.get(check.variable)
        items: list[str] = []
        for root, order in roots:
            rendered = _render(root)
            if rendered is None:
                return _unresolved("denominator factors are unsupported", check)
            outside = domain is not None and root.is_Rational and not domain.accepts(root)
            items.append(
                f"{check.variable} = {rendered}: pole of order {order}"
                + ("; outside the active domain" if outside else "")
            )
        return _proved(
            check,
            "; ".join(items),
            (),
            _unique((*shape.uses, *obligation_uses)),
            conditions=obligation_conditions,
        )
    if check.kind == "sign":
        chart = _sign_chart(shape, reasoning)
        return (
            _proved(
                check,
                chart[0],
                chart[1],
                _unique((*shape.uses, *chart[2], *obligation_uses)),
                conditions=obligation_conditions,
            )
            if chart
            else _unresolved("exact factor sign chart is unsupported", check)
        )
    fact = reasoning.facts.get(check.variable)
    if fact is None:
        return QueryAnswer(
            check=check,
            conclusion="inapplicable",
            blockers=("realness of the query variable is not proved",),
        )
    transformed = (
        property_difference(shape.value, shape.variable)
        if fact.integer
        else property_derivative(shape.value, shape.variable)
    )
    derivative_shape = (
        _shape_value(
            transformed,
            check.variable,
            shape.original_denominators,
            shape.original_denominator_expressions,
            shape.uses,
        )
        if transformed is not None
        else None
    )
    if derivative_shape is None:
        return _unresolved("guarded monotonicity transformation exceeds its bound", check)
    chart = _sign_chart(derivative_shape, reasoning)
    if chart is None:
        return _unresolved("exact factor sign chart is unsupported", check)
    _, intervals, uses = chart
    directional = tuple(
        item for item in intervals if item.endswith("positive") or item.endswith("negative")
    )
    zeros = tuple(item for item in intervals if item.endswith("zero"))
    label = "integer forward difference" if fact.integer else "derivative"
    return _proved(
        check,
        f"monotonicity by {label}",
        directional + zeros,
        _unique((*shape.uses, *uses, *obligation_uses)),
        conditions=obligation_conditions,
    )


def limit_answer(
    expression: Expression, query: LimitQuery, reasoning: ReasoningContext | None
) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound")
    shape = _shape(expression, query.variable, reasoning, subject="limit target")
    if isinstance(shape, QueryDiagnostic):
        return _unresolved(shape.render())
    obligation = _parameter_denominator_obligations(shape, reasoning)
    if obligation is None:
        return _unresolved("original denominator is not proved nonzero")
    obligation_conditions, obligation_uses = obligation
    if str(query.point) in {"oo", "-oo"}:
        answer = _infinite_limit(shape, str(query.point) == "oo", reasoning)
        if answer is None:
            return _unresolved("polynomial-degree limit is unsupported")
        return _with_denominator_obligations(answer, obligation_conditions, obligation_uses)
    exact = parse_exact_scalar(str(query.point))
    if exact is None:
        return _unresolved("limit point is invalid")
    point = sympy.Rational(exact.numerator, exact.denominator)
    denominator_at_point = property_substitute(shape.denominator, shape.variable, point)
    if denominator_at_point is None:
        return _unresolved("exact substitution is unsupported")
    if denominator_at_point != 0:
        value = property_substitute(shape.value, shape.variable, point)
        rendered = _render_supported_value(value, reasoning)
        if rendered is None:
            return _unresolved("exact substitution is unsupported")
        return _with_denominator_obligations(
            _limit_proved(
                shape, LimitEvidence(exists=True, value=rendered, left=rendered, right=rendered)
            ),
            obligation_conditions,
            obligation_uses,
        )
    roots = _roots(shape.denominator, shape.variable)
    order = next((count for root, count in roots or () if root == point), None)
    if order is None:
        return _unresolved("limit cancellation is unsupported")
    coefficient = property_local_pole_coefficient(
        shape.numerator, shape.denominator, shape.variable, point, order
    )
    signed_coefficient = _known_sign_with_uses(coefficient, reasoning)
    if signed_coefficient is None or signed_coefficient[0] == 0:
        return _unresolved("local pole coefficient is unsupported")
    sign, sign_uses = signed_coefficient
    right_positive = sign > 0
    left_positive = right_positive if order % 2 == 0 else not right_positive
    left, right = ("oo" if left_positive else "-oo"), ("oo" if right_positive else "-oo")
    evidence = LimitEvidence(
        exists=left == right,
        value=left if left == right else None,
        left=left if query.direction != "right" else None,
        right=right if query.direction != "left" else None,
    )
    if query.direction == "left":
        evidence = evidence.model_copy(update={"exists": True, "value": left})
    if query.direction == "right":
        evidence = evidence.model_copy(update={"exists": True, "value": right})
    return _with_denominator_obligations(
        _limit_proved(shape, evidence),
        obligation_conditions,
        _unique((*obligation_uses, *sign_uses)),
    )


def _shape(
    expression: Expression,
    variable_name: str | None,
    reasoning: ReasoningContext,
    *,
    subject: str,
) -> RationalShape | QueryDiagnostic:
    recovery = "use a smaller univariate rational target"
    try:
        applied = reasoning.apply(expression)
    except Exception:
        return QueryDiagnostic(
            subject, "cannot be prepared by bounded query reasoning", recovery=recovery
        )
    measurement = rational_ir_measure(applied)
    if isinstance(measurement, RationalMeasureFailure):
        return QueryDiagnostic(
            subject,
            RATIONAL_FAILURE_REASONS[measurement.kind],
            measurement.observed,
            measurement.configured,
            recovery,
        )
    raw = property_value(applied)
    if raw is None:
        return QueryDiagnostic(
            subject, "cannot be translated by the bounded rational backend", recovery=recovery
        )
    cancelled = property_cancel(raw)
    if cancelled is None:
        return QueryDiagnostic(
            subject, "cannot be cancelled by the bounded rational backend", recovery=recovery
        )
    symbols = tuple(cancelled.free_symbols)
    if variable_name is None:
        # A denominator that is independent of the chart axis is an obligation,
        # not a competing axis (for example x/a).
        denominator_symbols = {
            symbol
            for item in collect_denominators(applied)
            if (value := property_value(item)) is not None and value.free_symbols
            for symbol in value.free_symbols
        }
        # A single symbol remains the chart axis even if its active domain gives
        # it a sign; otherwise only the one non-parameter symbol may be the axis.
        axes = (
            symbols
            if len(symbols) == 1
            else [
                symbol
                for symbol in symbols
                if symbol not in denominator_symbols
                and not _fact_has_definite_sign(reasoning.facts.get(str(symbol)))
            ]
        )
        if len(axes) != 1:
            return QueryDiagnostic(
                "sign property axis",
                "is ambiguous",
                recovery="reduce to one unambiguous variable",
            )
        variable = axes[0]
    else:
        variable = sympy.Symbol(variable_name)
    original_expressions = collect_denominators(applied)
    originals = tuple(
        value for item in original_expressions if (value := property_value(item)) is not None
    )
    source_value = property_value(expression)
    participating = (
        tuple(str(symbol) for symbol in source_value.free_symbols)
        if source_value is not None
        else ()
    )
    # Shape records only replacements. Domain and sign facts belong to the proof
    # operation that consumes them, never to normalization.
    uses = reasoning.application_uses(participating)
    shape = _shape_value(cancelled, variable, originals, original_expressions, uses)
    if shape is None:
        return QueryDiagnostic(
            subject,
            "cannot be split into a bounded rational fraction",
            recovery=recovery,
        )
    return shape


def _parameter_denominator_obligations(
    shape: RationalShape, reasoning: ReasoningContext
) -> tuple[tuple[str, ...], tuple[RelationshipUse, ...]] | None:
    conditions: list[str] = []
    uses: tuple[RelationshipUse, ...] = ()
    for expression in shape.original_denominator_expressions:
        value = property_value(expression)
        if value is None:
            return None
        if shape.variable in value.free_symbols or not value.free_symbols:
            continue
        rendered = _render(value)
        proved, proof_uses = reasoning.prove_nonzero(expression)
        if rendered is None or not proved:
            return None
        condition = f"{rendered} != 0"
        if condition not in conditions:
            conditions.append(condition)
        uses = _unique((*uses, *proof_uses))
    return tuple(conditions), uses


def _shape_value(
    value: Any | None,
    variable: Any,
    originals: tuple[Any, ...],
    original_expressions: tuple[Expression, ...],
    uses: tuple[RelationshipUse, ...],
) -> RationalShape | None:
    if value is None:
        return None
    fraction = property_fraction(value)
    if fraction is None:
        return None
    numerator, denominator = fraction
    return RationalShape(
        value,
        numerator,
        denominator,
        sympy.Symbol(variable) if isinstance(variable, str) else variable,
        originals,
        original_expressions,
        uses,
    )


def _roots(value: Any, variable: Any) -> tuple[tuple[Any, int], ...] | None:
    roots = property_factor_roots(value, variable)
    if roots is None:
        return None
    return _sort_roots(roots)


def _all_roots(values: tuple[Any, ...], variable: Any) -> tuple[tuple[Any, int], ...] | None:
    roots: list[tuple[Any, int]] = []
    identities: set[str] = set()
    for value in values:
        found = _roots(value, variable)
        if found is None:
            return None
        for root, order in found:
            identity = _render(root)
            if identity is None:
                return None
            if identity not in identities:
                identities.add(identity)
                roots.append((root, order))
    return _sort_roots(tuple(roots))


def _sort_roots(roots: tuple[tuple[Any, int], ...]) -> tuple[tuple[Any, int], ...]:
    if not all(root.is_Rational for root, _ in roots):
        return roots
    return tuple(sorted(roots, key=lambda item: Fraction(int(item[0].p), int(item[0].q))))


def _sign_chart(
    shape: RationalShape, reasoning: ReasoningContext
) -> tuple[str, tuple[str, ...], tuple[RelationshipUse, ...]] | None:
    roots_n, roots_d = (
        _roots(shape.numerator, shape.variable),
        _roots(shape.denominator, shape.variable),
    )
    if (
        roots_n is None
        or roots_d is None
        or not all(root.is_Rational for root, _ in (*roots_n, *roots_d))
    ):
        return None
    roots = sorted(
        {root for root, _ in (*roots_n, *roots_d)},
        key=lambda root: Fraction(int(root.p), int(root.q)),
    )
    uses: list[RelationshipUse] = []
    fact = reasoning.facts.get(str(shape.variable))
    intervals: list[str] = []
    boundaries = (None, *roots, None)
    for index, (left, right) in enumerate(pairwise(boundaries)):
        point = _domain_interior_point(left, right, fact)
        if point is None:
            continue
        # The active domain selects each interior witness, so its retained
        # bounds are proof provenance for the chart (not for shape creation).
        if fact is not None:
            uses.extend(fact.sources)
        signed_numerator = _factor_sign_at(shape.numerator, shape.variable, point, reasoning)
        signed_denominator = _factor_sign_at(shape.denominator, shape.variable, point, reasoning)
        if signed_numerator is None or signed_denominator is None:
            return None
        numerator_sign, numerator_uses = signed_numerator
        denominator_sign, denominator_uses = signed_denominator
        sign = numerator_sign * denominator_sign
        if sign == 0:
            return None
        uses.extend((*numerator_uses, *denominator_uses))
        intervals.append(f"{_interval(index, roots)}: {'positive' if sign > 0 else 'negative'}")
    for root, _ in roots_n:
        if not any(root == pole for pole, _ in roots_d) and (fact is None or fact.accepts(root)):
            intervals.append(f"{_number(root)}: zero")
    return ("sign chart", tuple(intervals), _unique(tuple(uses))) if intervals else None


def _factor_sign_at(
    value: Any, variable: Any, point: Any, reasoning: ReasoningContext
) -> tuple[int, tuple[RelationshipUse, ...]] | None:
    """Compose signs only from isolated parameter factors and univariate factors."""
    factors = property_factor_components(value)
    if factors is None:
        return None
    sign: int = 1
    uses: tuple[RelationshipUse, ...] = ()
    for factor, multiplicity in factors:
        if variable in factor.free_symbols:
            # A parameter in a variable-bearing factor moves a root and is never
            # replaced by a same-sign witness.
            if factor.free_symbols != {variable}:
                return None
            evaluated = property_substitute(factor, variable, point)
            factor_sign = _known_rational_sign(evaluated)
            factor_uses: tuple[RelationshipUse, ...] = ()
        else:
            proved = _known_sign_with_uses(factor, reasoning)
            if proved is None:
                return None
            factor_sign, factor_uses = proved
        if factor_sign is None or factor_sign == 0:
            return None
        sign *= factor_sign if multiplicity % 2 else 1
        uses = _unique((*uses, *factor_uses))
    return sign, uses


def _domain_interior_point(
    left: Any | None, right: Any | None, fact: DomainFact | None
) -> Any | None:
    lower = Fraction(int(left.p), int(left.q)) if left is not None else None
    upper = Fraction(int(right.p), int(right.q)) if right is not None else None
    if fact is not None:
        if fact.lower is not None and (lower is None or fact.lower > lower):
            lower = fact.lower
        if fact.upper is not None and (upper is None or fact.upper < upper):
            upper = fact.upper
    if fact is not None and fact.integer:
        # Open chart cells need an integer representative, not merely a rational
        # midpoint (for example (-1/2, oo) contains 0).
        candidate = (
            Fraction((lower.numerator // lower.denominator) + 1)
            if lower is not None
            else Fraction(0)
        )
        if upper is not None and candidate >= upper:
            return None
    elif lower is not None and upper is not None:
        if lower >= upper:
            return None
        candidate = (lower + upper) / 2
    elif lower is not None:
        candidate = lower + 1
    elif upper is not None:
        candidate = upper - 1
    else:
        candidate = Fraction(0)
    point = sympy.Rational(candidate.numerator, candidate.denominator)
    if (left is not None and point <= left) or (right is not None and point >= right):
        return None
    return point if fact is None or fact.accepts(point) else None  # pyright: ignore[reportArgumentType]


def _infinite_limit(
    shape: RationalShape, positive: bool, reasoning: ReasoningContext
) -> QueryAnswer | None:
    info = property_polynomial_info(shape.numerator, shape.denominator, shape.variable)
    if info is None:
        return None
    numerator_degree, denominator_degree, leading = info
    degree = numerator_degree - denominator_degree
    sign_uses: tuple[RelationshipUse, ...] = ()
    if degree < 0:
        value = "0"
    elif degree == 0:
        value = _render_supported_value(leading, reasoning)
        if value is None:
            return None
    else:
        signed_leading = _known_sign_with_uses(leading, reasoning)
        if signed_leading is None or signed_leading[0] == 0:
            return None
        sign, sign_uses = signed_leading
        value = "oo" if sign * (1 if positive or degree % 2 == 0 else -1) > 0 else "-oo"
    return _with_denominator_obligations(
        _limit_proved(
            shape,
            LimitEvidence(
                exists=True,
                value=value,
                left=value if not positive else None,
                right=value if positive else None,
            ),
        ),
        (),
        sign_uses if degree > 0 else (),
    )


def _render_supported_value(value: Any | None, reasoning: ReasoningContext) -> str | None:
    if value is None:
        return None
    if value.is_Rational:
        return _number(value)
    if any(str(symbol) not in reasoning.facts for symbol in value.free_symbols):
        return None
    return property_render(value)


def _known_sign_with_uses(
    value: Any | None, reasoning: ReasoningContext
) -> tuple[int, tuple[RelationshipUse, ...]] | None:
    sign = _known_rational_sign(value)
    if sign is not None:
        return sign, ()
    if value is None:
        return None
    factors = property_factor_components(value)
    if factors is None:
        return None
    result, uses = 1, ()
    for factor, multiplicity in factors:
        rational = _known_rational_sign(factor)
        if rational is not None:
            factor_sign, factor_uses = rational, ()
        else:
            affine = property_affine_coefficients(factor)
            if affine is None:
                return None
            symbol, coefficient, constant = affine
            affine_sign, factor_uses = reasoning.affine_sign(symbol, coefficient, constant)
            if affine_sign is None:
                return None
            factor_sign = affine_sign
        result *= factor_sign if multiplicity % 2 else 1
        uses = _unique((*uses, *factor_uses))
    return result, uses


def _known_rational_sign(value: Any | None) -> int | None:
    if value is None or not value.is_Rational:
        return None
    return 1 if value > 0 else -1 if value < 0 else 0


def _fact_has_definite_sign(fact: DomainFact | None) -> bool:
    return _fact_is_strictly_positive(fact) or _fact_is_strictly_negative(fact)


def _fact_is_strictly_positive(fact: DomainFact | None) -> bool:
    return (
        fact is not None
        and fact.lower is not None
        and (fact.lower > 0 or (fact.lower == 0 and fact.lower_strict))
    )


def _fact_is_strictly_negative(fact: DomainFact | None) -> bool:
    return (
        fact is not None
        and fact.upper is not None
        and (fact.upper < 0 or (fact.upper == 0 and fact.upper_strict))
    )


def _fact_is_zero(fact: DomainFact) -> bool:
    return fact.lower == fact.upper == 0


def _afmm_conditions(p_fact: DomainFact | None, q_fact: DomainFact | None) -> bool:
    return bool(
        p_fact is not None
        and p_fact.integer
        and p_fact.lower is not None
        and p_fact.lower >= 0
        and q_fact is not None
        and q_fact.lower is not None
        and q_fact.lower >= 0
        and q_fact.upper is not None
        and (q_fact.upper < 1 or (q_fact.upper == 1 and q_fact.upper_strict))
    )


def _is_afmm_tail(expression: Expression) -> bool:
    return (
        isinstance(expression, Sum)
        and isinstance(expression.upper, InfinityLiteral)
        and expression.upper.sign > 0
        and isinstance(expression.lower, Symbol)
        and _afmm_ratio(expression.body, expression.index) is not None
    )


def _afmm_ratio(body: Expression, index: str) -> str | None:
    if not isinstance(body, BinaryExpression) or body.operator is not BinaryOperator.MULTIPLY:
        return None
    for linear, power in ((body.left, body.right), (body.right, body.left)):
        if (
            _is_k_plus_one(linear, index)
            and isinstance(power, BinaryExpression)
            and power.operator is BinaryOperator.POWER
            and isinstance(power.left, Symbol)
            and isinstance(power.right, Symbol)
            and power.right.name == index
        ):
            return power.left.name
    return None


def _is_k_plus_one(value: Expression, index: str) -> bool:
    return (
        isinstance(value, BinaryExpression)
        and value.operator is BinaryOperator.ADD
        and (
            (
                isinstance(value.left, Symbol)
                and value.left.name == index
                and getattr(value.right, "value", None) == 1
            )
            or (
                isinstance(value.right, Symbol)
                and value.right.name == index
                and getattr(value.left, "value", None) == 1
            )
        )
    )


def _render(value: Any) -> str | None:
    return _number(value) if value.is_Rational else property_render(value)


def _number(value: Any) -> str:
    return render_exact(ExactRational(int(value.p), int(value.q)))


def _interval(index: int, roots: list[Any]) -> str:
    left = "-oo" if index == 0 else _number(roots[index - 1])
    right = "oo" if index == len(roots) else _number(roots[index])
    return f"({left}, {right})"


def _with_denominator_obligations(
    answer: QueryAnswer,
    conditions: tuple[str, ...],
    uses: tuple[RelationshipUse, ...],
) -> QueryAnswer:
    all_uses = _unique((*answer.assumptions_used, *uses))
    return answer.model_copy(
        update={
            "conclusion": "proved_under_assumptions" if all_uses else answer.conclusion,
            "conditions": tuple(dict.fromkeys((*answer.conditions, *conditions))),
            "assumptions_used": all_uses,
        }
    )


def _limit_proved(shape: RationalShape, evidence: LimitEvidence) -> QueryAnswer:
    return QueryAnswer(
        conclusion="proved_under_assumptions" if shape.uses else "proved",
        assumptions_used=shape.uses,
        evidence=evidence,
    )


def _unique(
    values: tuple[RelationshipUse, ...] | list[RelationshipUse],
) -> tuple[RelationshipUse, ...]:
    return tuple(dict.fromkeys(values))


def _proved(
    check: PropertyCheck,
    value: str,
    intervals: tuple[str, ...] = (),
    uses: tuple[RelationshipUse, ...] = (),
    *,
    conditions: tuple[str, ...] = (),
) -> QueryAnswer:
    return QueryAnswer(
        check=check,
        conclusion="proved_under_assumptions" if uses else "proved",
        conditions=conditions,
        assumptions_used=uses,
        evidence=PropertyEvidence(value=value, intervals=intervals),
    )


def _unresolved(blocker: str, check: PropertyCheck | None = None) -> QueryAnswer:
    return QueryAnswer(check=check, conclusion="unresolved", blockers=(blocker,))
