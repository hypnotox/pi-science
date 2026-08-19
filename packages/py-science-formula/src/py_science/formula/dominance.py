# pyright: basic, reportArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportOptionalOperand=false, reportUnnecessaryComparison=false
"""Bounded policy for dominance over retained aggregate abstract work.

This module deliberately owns report policy.  SymPy is used only to normalize
and evaluate the already retained work expression; it never receives a public
request or decides admissibility on its own.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, pairwise
from math import ceil, floor
from typing import Any

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.models import (
    DominanceAnalysisRequest,
    DominanceAnalysisSuccess,
    DominanceEvidence,
    DominanceExclusion,
    DominanceIntegerRangeCell,
    DominanceIntervalCell,
    DominancePointCell,
    DominanceRange,
    DominanceTerm,
    MathematicalDomain,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sign_chart import ExplicitAxis, explicit_axis_sign_chart
from py_science.formula.sympy_backend import property_value

MAX_DOMINANCE_TERMS = 16
MAX_DOMINANCE_PAIRS = 120
MAX_DOMINANCE_POINTS = 256
MAX_DOMINANCE_CELLS = 513
MAX_DOMINANCE_RENDER_BYTES = 65_536
MAX_DOMINANCE_SUPPLEMENT_BYTES = 65_536


def _f(text: str) -> Fraction | None:
    if text in {"-oo", "oo"}:
        return None
    return Fraction(text)


def _s(value: Fraction | None, positive: bool = False) -> str:
    if value is None:
        return "oo" if positive else "-oo"
    return (
        str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    )


def _domain_range(
    domain: MathematicalDomain,
) -> tuple[Fraction | None, Fraction | None, bool, bool]:
    if domain in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL}:
        return Fraction(0), None, False, False
    if domain in {MathematicalDomain.NONNEGATIVE_INTEGER, MathematicalDomain.NONNEGATIVE_REAL}:
        return Fraction(0), None, True, False
    return None, None, False, False


def _intersect(
    request: DominanceAnalysisRequest,
) -> tuple[DominanceRange | None, tuple[Fraction | None, Fraction | None, bool, bool]]:
    lower, upper, li, ui = _domain_range(request.variables[request.axis].domain)
    if request.range is not None:
        rl, ru = _f(request.range.lower), _f(request.range.upper)
        if rl is not None and (
            lower is None or rl > lower or (rl == lower and not request.range.lower_inclusive)
        ):
            lower, li = rl, request.range.lower_inclusive
        if ru is not None and (
            upper is None or ru < upper or (ru == upper and not request.range.upper_inclusive)
        ):
            upper, ui = ru, request.range.upper_inclusive
    empty = (
        lower is not None
        and upper is not None
        and (lower > upper or (lower == upper and not (li and ui)))
    )
    effective = DominanceRange(
        lower=_s(lower), upper=_s(upper, True), lower_inclusive=li, upper_inclusive=ui
    )
    return (None if empty else effective), (lower, upper, li, ui)


def _unresolved(
    request: DominanceAnalysisRequest, analysis: Any, effective: DominanceRange, blocker: str
) -> DominanceAnalysisSuccess:
    return DominanceAnalysisSuccess(
        analysis=analysis,
        axis=request.axis,
        fixed={name: str(value) for name, value in request.fixed.items()},
        requested_range=request.range,
        effective_range=effective,
        dominance_status="unresolved",
        blockers=(blocker,),
    )


def analyze_retained(request: DominanceAnalysisRequest, computed: Any) -> DominanceAnalysisSuccess:
    analysis = computed.success
    effective, bounds = _intersect(request)
    # An integer interval can be real-nonempty but have no lattice points.
    integer = request.variables[request.axis].domain.is_integer
    lo, hi, li, ui = bounds
    if effective is None or (
        integer
        and lo is not None
        and hi is not None
        and (
            ceil(lo) > floor(hi)
            or (ceil(lo) == floor(hi) and (not li or not ui) and Fraction(ceil(lo)) == lo == hi)
        )
    ):
        return DominanceAnalysisSuccess(
            analysis=analysis,
            axis=request.axis,
            fixed={name: str(value) for name, value in request.fixed.items()},
            requested_range=request.range,
            effective_range=DominanceRange(
                lower=_s(lo), upper=_s(hi, True), lower_inclusive=li, upper_inclusive=ui
            ),
            dominance_status="empty",
        )
    if computed.aggregate_analysis.unknown_costs:
        return _unresolved(
            request, analysis, effective, "aggregate work contains unknown primitive costs"
        )
    if computed.aggregate_analysis.unresolved:
        return _unresolved(request, analysis, effective, "aggregate work is unresolved")
    if computed.aggregate_analysis.direct_work_blockers:
        return _unresolved(request, analysis, effective, "aggregate work is not finite")
    value = property_value(computed.aggregate_analysis.total_work)
    if value is None:
        return _unresolved(
            request, analysis, effective, "aggregate work rational form is unsupported"
        )
    axis = sympy.Symbol(request.axis)
    try:
        substitutions = {
            sympy.Symbol(name): sympy.Rational(Fraction(value))
            for name, value in request.fixed.items()
        }
        value = sympy.cancel(value.subs(substitutions))
        numerator, denominator = sympy.fraction(value)
        if any(symbol != axis for symbol in value.free_symbols):
            return _unresolved(
                request, analysis, effective, "aggregate work has unsupported non-axis coefficients"
            )
        if numerator == 0:
            return DominanceAnalysisSuccess(
                analysis=analysis,
                axis=request.axis,
                fixed={name: str(value) for name, value in request.fixed.items()},
                requested_range=request.range,
                effective_range=effective,
                shared_denominator="1",
                dominance_status="complete",
                conditions=("aggregate work is identically zero",),
            )
        poly = sympy.Poly(numerator, axis)
        if poly is None or any(power < 0 for (power,) in poly.monoms()):
            return _unresolved(
                request, analysis, effective, "aggregate work polynomial numerator is unsupported"
            )
        items = [
            (power[0], coefficient)
            for power, coefficient in zip(poly.monoms(), poly.coeffs(), strict=True)
            if coefficient != 0
        ]
    except Exception:
        return _unresolved(request, analysis, effective, "aggregate work rational backend failed")
    if len(items) > MAX_DOMINANCE_TERMS:
        return _unresolved(request, analysis, effective, "dominance term bound exceeded")
    terms = tuple(
        DominanceTerm(
            id=f"power:{power}",
            power=power,
            coefficient=str(coefficient),
            expression=str(coefficient * axis**power),
        )
        for power, coefficient in items
    )
    rendered = sum(
        len(term.coefficient.encode()) + len(term.expression.encode()) for term in terms
    ) + len(str(denominator).encode())
    if rendered > MAX_DOMINANCE_RENDER_BYTES:
        return _unresolved(request, analysis, effective, "dominance rendering bound exceeded")
    # Reconstruction is deliberately independent of collection before publication.
    if (
        sympy.expand(sum(coefficient * axis**power for power, coefficient in items) - numerator)
        != 0
    ):
        return _unresolved(request, analysis, effective, "dominance reconstruction failed")
    boundaries: set[Fraction] = set()
    exclusions: set[Fraction] = set()
    try:
        for root in sympy.roots(denominator, axis):
            if root.is_Rational:
                exclusions.add(Fraction(int(root.p), int(root.q)))
        evidence: list[DominanceEvidence] = []
        reasoning = ReasoningContext.build(
            {request.axis: request.variables[request.axis].domain}, (), ()
        )
        for left, right in combinations(terms, 2):
            a, b = items[terms.index(left)], items[terms.index(right)]
            difference = sympy.expand((a[1] * axis ** a[0]) ** 2 - (b[1] * axis ** b[0]) ** 2)
            chart = explicit_axis_sign_chart(
                difference, sympy.Integer(1), ExplicitAxis(request.axis, integer), reasoning
            )
            if chart.refusal is not None:
                return _unresolved(request, analysis, effective, chart.refusal.reason)
            boundaries.update(item.value for item in chart.roots)
            evidence.append(DominanceEvidence(pair=(left.id, right.id), difference=str(difference)))
    except Exception:
        return _unresolved(request, analysis, effective, "dominance comparison backend failed")
    if len(evidence) > MAX_DOMINANCE_PAIRS:
        return _unresolved(request, analysis, effective, "dominance pair bound exceeded")
    finite = {
        x for x in boundaries | exclusions if (lo is None or x >= lo) and (hi is None or x <= hi)
    }
    if lo is not None:
        finite.add(lo)
    if hi is not None:
        finite.add(hi)
    if len(finite) > MAX_DOMINANCE_POINTS:
        return _unresolved(request, analysis, effective, "dominance partition-point bound exceeded")
    cells = _cells(items, terms, sorted(finite), exclusions, lo, hi, li, ui, integer)
    if len(cells) > MAX_DOMINANCE_CELLS:
        return _unresolved(request, analysis, effective, "dominance cell bound exceeded")
    active = {item for cell in cells for item in cell.dominant}
    result = DominanceAnalysisSuccess(
        analysis=analysis,
        axis=request.axis,
        fixed={name: str(value) for name, value in request.fixed.items()},
        requested_range=request.range,
        effective_range=effective,
        shared_denominator=str(denominator),
        terms=terms,
        cells=tuple(cells),
        exclusions=tuple(
            DominanceExclusion(value=_s(item))
            for item in sorted(exclusions)
            if (lo is None or item >= lo) and (hi is None or item <= hi)
        ),
        never_dominant=tuple(term.id for term in terms if term.id not in active),
        evidence=tuple(evidence),
        dominance_status="complete",
    )
    if (
        len(result.model_dump_json().encode()) - len(analysis.model_dump_json().encode())
        > MAX_DOMINANCE_SUPPLEMENT_BYTES
    ):
        return _unresolved(request, analysis, effective, "dominance supplement bound exceeded")
    return result


def _cells(
    items: list[tuple[int, Any]],
    terms: tuple[DominanceTerm, ...],
    points: list[Fraction],
    exclusions: set[Fraction],
    lo: Fraction | None,
    hi: Fraction | None,
    li: bool,
    ui: bool,
    integer: bool,
) -> list[Any]:
    cuts = [x for x in points if x not in exclusions]
    bounds = [None, *cuts, None]
    cells: list[Any] = []

    def winners(value: Fraction) -> tuple[str, ...]:
        scores = [
            abs(coefficient * sympy.Rational(value.numerator, value.denominator) ** power)
            for power, coefficient in items
        ]
        maximum = max(scores)
        return tuple(term.id for term, score in zip(terms, scores, strict=True) if score == maximum)

    if integer:
        low = -(10**9) if lo is None else ceil(lo) + (0 if li or Fraction(ceil(lo)) > lo else 1)
        high = 10**9 if hi is None else floor(hi) - (0 if ui or Fraction(floor(hi)) < hi else 1)
        # Roots partition lattice ranges; sentinel infinities stay compact.
        starts = [low, *(floor(x) + 1 for x in cuts), high + 1]
        for a, b in pairwise(starts):
            if a >= b:
                continue
            sample = a
            cells.append(
                DominanceIntegerRangeCell(
                    lower="-oo" if a == -(10**9) else str(a),
                    upper="oo" if b - 1 == 10**9 else str(b - 1),
                    dominant=winners(Fraction(sample)),
                )
            )
        for x in cuts:
            if x.denominator == 1 and low <= x <= high and x not in exclusions:
                cells.append(
                    DominancePointCell(kind="integer_point", value=_s(x), dominant=winners(x))
                )
        return cells
    for a, b in pairwise(bounds):
        if a is not None and b is not None and a >= b:
            continue
        sample = (
            (a + b) / 2
            if a is not None and b is not None
            else a + 1
            if a is not None
            else b - 1
            if b is not None
            else Fraction(0)
        )
        cells.append(
            DominanceIntervalCell(
                lower=_s(a),
                upper=_s(b, True),
                lower_inclusive=False,
                upper_inclusive=False,
                dominant=winners(sample),
            )
        )
    for x in cuts:
        if x not in exclusions and (lo is None or x > lo or li) and (hi is None or x < hi or ui):
            cells.append(DominancePointCell(kind="real_point", value=_s(x), dominant=winners(x)))
    return cells
