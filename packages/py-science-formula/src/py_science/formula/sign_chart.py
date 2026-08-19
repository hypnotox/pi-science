"""Typed, bounded structural sign charts over one explicitly declared axis.

This module owns chart admissibility and witnesses.  SymPy is used only through
checked backend helpers; callers receive structural facts rather than rendered
property evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Any, Literal

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.models import RelationshipUse
from py_science.formula.reasoning import DomainFact, ReasoningContext
from py_science.formula.sympy_backend import (
    property_affine_coefficients,
    property_factor_components,
    property_factor_roots,
    property_substitute,
)


@dataclass(frozen=True, slots=True)
class ExplicitAxis:
    """The caller-declared axis; chart construction never infers one."""

    name: str
    integer: bool


@dataclass(frozen=True, slots=True)
class ExactBoundary:
    value: Fraction
    kind: Literal["root", "pole"]
    order: int
    original_denominator: bool = False


@dataclass(frozen=True, slots=True)
class ChartInterval:
    left: Fraction | None
    right: Fraction | None
    sign: Literal[-1, 1]


@dataclass(frozen=True, slots=True)
class ChartPoint:
    value: Fraction
    sign: Literal[-1, 0, 1]


@dataclass(frozen=True, slots=True)
class ChartRefusal:
    reason: str


@dataclass(frozen=True, slots=True)
class StructuralSignChart:
    axis: ExplicitAxis
    roots: tuple[ExactBoundary, ...]
    poles: tuple[ExactBoundary, ...]
    intervals: tuple[ChartInterval, ...]
    points: tuple[ChartPoint, ...]
    provenance: tuple[RelationshipUse, ...]
    refusal: ChartRefusal | None = None


def explicit_axis_sign_chart(
    numerator: Any,
    denominator: Any,
    axis: ExplicitAxis,
    reasoning: ReasoningContext,
    *,
    original_denominators: tuple[Any, ...] = (),
    ignore_nonreal_roots: bool = False,
) -> StructuralSignChart:
    """Return the bounded sign chart for checked rational components.

    ``original_denominators`` are retained as exclusion obligations even after
    cancellation. They are structural poles, but only reduced denominator
    poles participate in ordinary value-sign rendering.
    """
    try:
        return _build_explicit_axis_sign_chart(
            numerator,
            denominator,
            axis,
            reasoning,
            original_denominators,
            ignore_nonreal_roots,
        )
    except Exception:
        return _refused(axis, "sign chart backend failed")


def _build_explicit_axis_sign_chart(
    numerator: Any,
    denominator: Any,
    axis: ExplicitAxis,
    reasoning: ReasoningContext,
    original_denominators: tuple[Any, ...],
    ignore_nonreal_roots: bool,
) -> StructuralSignChart:
    variable = sympy.Symbol(axis.name)
    roots_n = _roots(numerator, variable, ignore_nonreal=ignore_nonreal_roots)
    roots_d = _roots(denominator, variable, ignore_nonreal=ignore_nonreal_roots)
    if roots_n is None or roots_d is None:
        return _refused(axis, "exact factor sign chart is unsupported")

    original: list[tuple[Any, int]] = []
    for value in original_denominators:
        roots = _roots(value, variable, ignore_nonreal=ignore_nonreal_roots)
        if roots is None:
            return _refused(axis, "original denominator roots are unsupported")
        original.extend(roots)

    fact = reasoning.facts.get(axis.name)
    if fact is not None and fact.integer != axis.integer:
        return _refused(axis, "explicit axis domain is inconsistent")

    root_values = {root for root, _ in roots_n}
    reduced_poles = {root for root, _ in roots_d}
    boundaries = sorted(root_values | reduced_poles, key=_fraction)
    uses: list[RelationshipUse] = []
    intervals: list[ChartInterval] = []
    for left, right in pairwise((None, *boundaries, None)):
        witness = _interior(left, right, fact, integer=axis.integer)
        if witness is None:
            continue
        if fact is not None:
            uses.extend(fact.sources)
        numerator_sign = _factor_sign(numerator, variable, witness, reasoning)
        denominator_sign = _factor_sign(denominator, variable, witness, reasoning)
        if numerator_sign is None or denominator_sign is None:
            return _refused(axis, "exact factor sign chart is unsupported", uses)
        sign, numerator_uses = numerator_sign
        other, denominator_uses = denominator_sign
        if sign * other == 0:
            return _refused(axis, "exact factor sign chart is unsupported", uses)
        uses.extend((*numerator_uses, *denominator_uses))
        intervals.append(
            ChartInterval(
                _as_fraction(left),
                _as_fraction(right),
                1 if sign * other > 0 else -1,
            )
        )
    roots = tuple(ExactBoundary(_fraction(root), "root", order) for root, order in roots_n)
    poles = tuple(ExactBoundary(_fraction(root), "pole", order) for root, order in roots_d) + tuple(
        ExactBoundary(_fraction(root), "pole", order, True)
        for root, order in original
        if root not in reduced_poles
    )
    points = tuple(
        ChartPoint(_fraction(root), 0)
        for root, _ in roots_n
        if root not in reduced_poles
        and (not axis.integer or root.q == 1)
        and (fact is None or fact.accepts(root))
    )
    return StructuralSignChart(
        axis,
        roots,
        poles,
        tuple(intervals),
        points,
        _unique(tuple(uses)),
    )


def _refused(
    axis: ExplicitAxis,
    reason: str,
    uses: list[RelationshipUse] | tuple[RelationshipUse, ...] = (),
) -> StructuralSignChart:
    return StructuralSignChart(
        axis,
        (),
        (),
        (),
        (),
        _unique(tuple(uses)),
        ChartRefusal(reason),
    )


def _roots(
    value: Any, variable: Any, *, ignore_nonreal: bool = False
) -> tuple[tuple[Any, int], ...] | None:
    roots = (
        property_factor_roots(value, variable, ignore_nonreal=True)
        if ignore_nonreal
        else property_factor_roots(value, variable)
    )
    if roots is None or not all(root.is_Rational for root, _ in roots):
        return None
    return tuple(sorted(roots, key=lambda item: _fraction(item[0])))


def _fraction(value: Any) -> Fraction:
    return Fraction(int(value.p), int(value.q))


def _as_fraction(value: Any | None) -> Fraction | None:
    return _fraction(value) if value is not None else None


def _factor_sign(
    value: Any,
    variable: Any,
    point: Any,
    reasoning: ReasoningContext,
) -> tuple[int, tuple[RelationshipUse, ...]] | None:
    factors = property_factor_components(value)
    if factors is None:
        return None
    sign, uses = 1, ()
    for factor, multiplicity in factors:
        if variable in factor.free_symbols:
            if factor.free_symbols != {variable}:
                return None
            factor_sign = _rational_sign(property_substitute(factor, variable, point))
            factor_uses: tuple[RelationshipUse, ...] = ()
        else:
            known = _known_sign(factor, reasoning)
            if known is None:
                return None
            factor_sign, factor_uses = known
        if factor_sign is None or factor_sign == 0:
            return None
        sign *= factor_sign if multiplicity % 2 else 1
        uses = _unique((*uses, *factor_uses))
    return sign, uses


def _known_sign(
    value: Any, reasoning: ReasoningContext
) -> tuple[int, tuple[RelationshipUse, ...]] | None:
    rational = _rational_sign(value)
    if rational is not None:
        return rational, ()
    if value is None or (factors := property_factor_components(value)) is None:
        return None
    sign, uses = 1, ()
    for factor, multiplicity in factors:
        factor_sign = _rational_sign(factor)
        factor_uses: tuple[RelationshipUse, ...] = ()
        if factor_sign is None:
            affine = property_affine_coefficients(factor)
            if affine is None:
                return None
            symbol, coefficient, constant = affine
            factor_sign, factor_uses = reasoning.affine_sign(symbol, coefficient, constant)
            if factor_sign is None:
                return None
        sign *= factor_sign if multiplicity % 2 else 1
        uses = _unique((*uses, *factor_uses))
    return sign, uses


def _rational_sign(value: Any | None) -> int | None:
    if value is None or not value.is_Rational:
        return None
    return 1 if value > 0 else -1 if value < 0 else 0


def _interior(
    left: Any | None,
    right: Any | None,
    fact: DomainFact | None,
    *,
    integer: bool,
) -> Any | None:
    lower, upper = _as_fraction(left), _as_fraction(right)
    if fact is not None and not integer:
        if fact.lower is not None and (lower is None or fact.lower > lower):
            lower = fact.lower
        if fact.upper is not None and (upper is None or fact.upper < upper):
            upper = fact.upper
    if integer:
        least = None if lower is None else _floor(lower) + 1
        greatest = None if upper is None else _ceil(upper) - 1
        if fact is not None and fact.lower is not None:
            domain_least = _floor(fact.lower) + 1 if fact.lower_strict else _ceil(fact.lower)
            least = domain_least if least is None else max(least, domain_least)
        if fact is not None and fact.upper is not None:
            domain_greatest = _ceil(fact.upper) - 1 if fact.upper_strict else _floor(fact.upper)
            greatest = domain_greatest if greatest is None else min(greatest, domain_greatest)
        if least is not None and greatest is not None and least > greatest:
            return None
        candidate = Fraction(least if least is not None else min(0, greatest or 0))
    else:
        if lower is not None and upper is not None:
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
    admissible = (
        (left is None or point > left)
        and (right is None or point < right)
        and (
            fact is None or fact.accepts(point)  # pyright: ignore[reportArgumentType]
        )
    )
    return point if admissible else None


def _floor(value: Fraction) -> int:
    return value.numerator // value.denominator


def _ceil(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _unique(values: tuple[RelationshipUse, ...]) -> tuple[RelationshipUse, ...]:
    return tuple({(item.name, item.relationship): item for item in values}.values())
