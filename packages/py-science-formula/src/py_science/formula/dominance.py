"""Bounded dominance policy over one retained aggregate abstract-work expression."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, pairwise
from math import ceil, floor
from typing import Any, Literal, cast

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
    RelationshipUse,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sign_chart import ExplicitAxis, explicit_axis_sign_chart
from py_science.formula.sympy_backend import (
    dominance_magnitudes,
    dominance_node_count,
    dominance_one,
    dominance_original_denominators,
    dominance_pair_difference,
    dominance_rational_form,
    dominance_reconstructs,
    dominance_term_expression,
    property_value,
)

MAX_DOMINANCE_TERMS = 16
MAX_DOMINANCE_PAIRS = 120
MAX_DOMINANCE_POINTS = 256
MAX_DOMINANCE_CELLS = 513
MAX_DOMINANCE_REASONING_STEPS = 4_096
MAX_DOMINANCE_INTERMEDIATE_NODES = 4_096
MAX_DOMINANCE_RENDER_BYTES = 65_536
MAX_DOMINANCE_SUPPLEMENT_BYTES = 65_536


def _fraction(text: str) -> Fraction | None:
    if text in {"-oo", "oo"}:
        return None
    return Fraction(text)


def _render(value: Fraction | None, *, upper: bool = False) -> str:
    if value is None:
        return "oo" if upper else "-oo"
    return str(value.numerator) if value.denominator == 1 else str(value)


def _domain_range(
    domain: MathematicalDomain,
) -> tuple[Fraction | None, Fraction | None, bool, bool]:
    if domain in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL}:
        return Fraction(0), None, False, False
    if domain in {MathematicalDomain.NONNEGATIVE_INTEGER, MathematicalDomain.NONNEGATIVE_REAL}:
        return Fraction(0), None, True, False
    return None, None, False, False


def _tighten_lower(
    current: Fraction | None,
    inclusive: bool,
    candidate: Fraction | None,
    candidate_inclusive: bool,
) -> tuple[Fraction | None, bool]:
    if candidate is None:
        return current, inclusive
    if current is None or candidate > current:
        return candidate, candidate_inclusive
    if candidate == current:
        return current, inclusive and candidate_inclusive
    return current, inclusive


def _tighten_upper(
    current: Fraction | None,
    inclusive: bool,
    candidate: Fraction | None,
    candidate_inclusive: bool,
) -> tuple[Fraction | None, bool]:
    if candidate is None:
        return current, inclusive
    if current is None or candidate < current:
        return candidate, candidate_inclusive
    if candidate == current:
        return current, inclusive and candidate_inclusive
    return current, inclusive


def _intersect(
    request: DominanceAnalysisRequest, reasoning: ReasoningContext
) -> tuple[DominanceRange | None, tuple[Fraction | None, Fraction | None, bool, bool]]:
    lower, upper, lower_inclusive, upper_inclusive = _domain_range(
        request.variables[request.axis].domain
    )
    fact = reasoning.facts.get(request.axis)
    if fact is not None:
        lower, lower_inclusive = _tighten_lower(
            lower, lower_inclusive, fact.lower, not fact.lower_strict
        )
        upper, upper_inclusive = _tighten_upper(
            upper, upper_inclusive, fact.upper, not fact.upper_strict
        )
    if request.range is not None:
        lower, lower_inclusive = _tighten_lower(
            lower,
            lower_inclusive,
            _fraction(request.range.lower),
            request.range.lower_inclusive,
        )
        upper, upper_inclusive = _tighten_upper(
            upper,
            upper_inclusive,
            _fraction(request.range.upper),
            request.range.upper_inclusive,
        )
    empty = lower is not None and upper is not None and (
        lower > upper
        or (lower == upper and not (lower_inclusive and upper_inclusive))
    )
    bounds = (lower, upper, lower_inclusive, upper_inclusive)
    if empty:
        return None, bounds
    return (
        DominanceRange(
            lower=_render(lower),
            upper=_render(upper, upper=True),
            lower_inclusive=lower_inclusive,
            upper_inclusive=upper_inclusive,
        ),
        bounds,
    )


def _integer_bounds(
    bounds: tuple[Fraction | None, Fraction | None, bool, bool],
) -> tuple[int | None, int | None]:
    lower, upper, lower_inclusive, upper_inclusive = bounds
    low = None if lower is None else ceil(lower) if lower_inclusive else floor(lower) + 1
    high = None if upper is None else floor(upper) if upper_inclusive else ceil(upper) - 1
    return low, high


def _unresolved(
    request: DominanceAnalysisRequest,
    analysis: Any,
    effective: DominanceRange,
    blocker: str,
    *,
    assumptions_used: tuple[RelationshipUse, ...] = (),
) -> DominanceAnalysisSuccess:
    return DominanceAnalysisSuccess(
        analysis=analysis,
        axis=request.axis,
        axis_domain=request.variables[request.axis].domain,
        fixed={name: str(value) for name, value in request.fixed.items()},
        requested_range=request.range,
        effective_range=effective,
        dominance_status="unresolved",
        blockers=(blocker,),
        assumptions_used=assumptions_used,
    )


def _unique_uses(values: list[RelationshipUse]) -> tuple[RelationshipUse, ...]:
    return tuple({(item.name, item.relationship): item for item in values}.values())


def _node_count(value: Any) -> int:
    return dominance_node_count(value, MAX_DOMINANCE_INTERMEDIATE_NODES)


def _reconstructs(items: list[tuple[int, Any]], numerator: Any, axis: str) -> bool:
    return dominance_reconstructs(items, numerator, axis)


def _active(
    value: Fraction,
    bounds: tuple[Fraction | None, Fraction | None, bool, bool],
) -> bool:
    lower, upper, lower_inclusive, upper_inclusive = bounds
    return (
        lower is None
        or value > lower
        or (value == lower and lower_inclusive)
    ) and (
        upper is None
        or value < upper
        or (value == upper and upper_inclusive)
    )


def analyze_retained(request: DominanceAnalysisRequest, computed: Any) -> DominanceAnalysisSuccess:
    """Analyze the immutable retained aggregate work from one ordinary analysis."""
    analysis = computed.success
    # A declared/requested empty domain is a proved fact independent of optional
    # assumption reasoning.  Preserve it even when the latter reaches its cap.
    base_effective, base_bounds = _intersect(
        request,
        ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()}, (), ()
        ),
    )
    base_low, base_high = _integer_bounds(base_bounds)
    if base_effective is None or (
        request.variables[request.axis].domain.is_integer
        and base_low is not None and base_high is not None and base_low > base_high
    ):
        return DominanceAnalysisSuccess(
            analysis=analysis,
            axis=request.axis,
            axis_domain=request.variables[request.axis].domain,
            fixed={name: str(value) for name, value in request.fixed.items()},
            requested_range=request.range,
            effective_range=None,
            dominance_status="empty",
        )
    try:
        reasoning = ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            computed.knowledge.definitions,
            computed.knowledge.assumptions,
        )
    except Exception:
        # The ordinary analysis remains valid; only the supplemental proof abstains.
        return _unresolved(
            request, analysis, base_effective, "dominance reasoning bound exceeded"
        )

    effective, bounds = _intersect(request, reasoning)
    integer = request.variables[request.axis].domain.is_integer
    integer_lower, integer_upper = _integer_bounds(bounds)
    empty_integer_lattice = (
        integer
        and integer_lower is not None
        and integer_upper is not None
        and integer_lower > integer_upper
    )
    if effective is None or empty_integer_lattice:
        return DominanceAnalysisSuccess(
            analysis=analysis,
            axis=request.axis,
            axis_domain=request.variables[request.axis].domain,
            fixed={name: str(value) for name, value in request.fixed.items()},
            requested_range=request.range,
            effective_range=None,
            dominance_status="empty",
        )
    if computed.aggregate_analysis.unknown_costs:
        return _unresolved(
            request, analysis, effective, "aggregate work contains unknown primitive costs"
        )
    # Direct non-finiteness is a more specific retained-work qualification than
    # the generic unresolved marker which may accompany it.
    if computed.aggregate_analysis.direct_work_blockers:
        return _unresolved(request, analysis, effective, "aggregate work is not finite")
    retained_unresolved = tuple(
        item
        for item in computed.aggregate_analysis.unresolved
        if not item.startswith("assumption ")
    )
    if retained_unresolved:
        return _unresolved(request, analysis, effective, "aggregate work is unresolved")
    original_value = property_value(computed.aggregate_analysis.total_work)
    if original_value is None:
        return _unresolved(
            request, analysis, effective, "aggregate work rational form is unsupported"
        )

    substitutions = {name: Fraction(str(value)) for name, value in request.fixed.items()}
    original_denominators = dominance_original_denominators(
        computed.aggregate_analysis.total_work, substitutions
    )
    if original_denominators is None:
        return _unresolved(
            request, analysis, effective, "original denominator obligations are unsupported"
        )
    try:
        specialized, _original_denominator, numerator, denominator, items = (
            dominance_rational_form(original_value, substitutions, request.axis)
        )
        if _node_count(specialized) > MAX_DOMINANCE_INTERMEDIATE_NODES:
            return _unresolved(
                request, analysis, effective, "dominance intermediate-node bound exceeded"
            )
        # Zero work still has to retain the original denominator obligations;
        # its complete result is constructed after the typed pole charts below.
    except ValueError as error:
        blocker = (
            "aggregate work has unsupported non-axis coefficients"
            if str(error) == "non-axis coefficients"
            else "aggregate work polynomial numerator is unsupported"
        )
        return _unresolved(request, analysis, effective, blocker)
    except Exception:
        return _unresolved(
            request, analysis, effective, "aggregate work rational backend failed"
        )

    if len(items) > MAX_DOMINANCE_TERMS:
        return _unresolved(request, analysis, effective, "dominance term bound exceeded")
    pair_count = len(items) * (len(items) - 1) // 2
    if pair_count > MAX_DOMINANCE_PAIRS:
        return _unresolved(request, analysis, effective, "dominance pair bound exceeded")
    if not _reconstructs(items, numerator, request.axis):
        return _unresolved(request, analysis, effective, "dominance reconstruction failed")

    terms = tuple(
        DominanceTerm(
            id=f"power:{power}",
            power=power,
            coefficient=str(coefficient),
            expression=str(dominance_term_expression(power, coefficient, request.axis)),
        )
        for power, coefficient in items
    )
    render_bytes = len(str(denominator).encode("utf-8")) + sum(
        len(term.coefficient.encode("utf-8")) + len(term.expression.encode("utf-8"))
        for term in terms
    )
    if render_bytes > MAX_DOMINANCE_RENDER_BYTES:
        return _unresolved(request, analysis, effective, "dominance rendering bound exceeded")

    boundaries: set[Fraction] = set()
    exclusions: set[Fraction] = set()
    assumptions: list[RelationshipUse] = []
    evidence: list[DominanceEvidence] = []
    pair_blockers: list[str] = []
    steps = 2
    try:
        for candidate_denominator in (*original_denominators, denominator):
            chart = explicit_axis_sign_chart(
                dominance_one(),
                candidate_denominator,
                ExplicitAxis(request.axis, integer),
                reasoning,
                ignore_nonreal_roots=True,
            )
            if chart.refusal is not None:
                return _unresolved(
                    request,
                    analysis,
                    effective,
                    "original denominator roots are unsupported",
                )
            exclusions.update(item.value for item in chart.poles)
            assumptions.extend(chart.provenance)
            steps += 1
        for index, ((left, left_item), (right, right_item)) in enumerate(
            combinations(zip(terms, items, strict=True), 2),
            start=1,
        ):
            if steps + index > MAX_DOMINANCE_REASONING_STEPS:
                return _unresolved(
                    request, analysis, effective, "dominance reasoning-step bound exceeded"
                )
            difference = dominance_pair_difference(
                left_item, right_item, request.axis
            )
            if _node_count(difference) > MAX_DOMINANCE_INTERMEDIATE_NODES:
                return _unresolved(
                    request,
                    analysis,
                    effective,
                    "dominance intermediate-node bound exceeded",
                )
            chart = explicit_axis_sign_chart(
                difference,
                dominance_one(),
                ExplicitAxis(request.axis, integer),
                reasoning,
                ignore_nonreal_roots=True,
            )
            if chart.refusal is not None:
                pair_blockers.append(chart.refusal.reason)
                continue
            boundaries.update(item.value for item in chart.roots)
            assumptions.extend(chart.provenance)
            interval_signs = {item.sign for item in chart.intervals}
            sign = cast(
                Literal[-1, 0, 1] | None,
                0
                if difference == 0
                else next(iter(interval_signs))
                if len(interval_signs) == 1
                else None,
            )
            rendered_difference = str(difference)
            render_bytes += len(rendered_difference.encode("utf-8"))
            evidence.append(
                DominanceEvidence(
                    pair=(left.id, right.id),
                    difference=rendered_difference,
                    sign=sign,
                    roots=tuple(_render(item.value) for item in chart.roots),
                )
            )
    except Exception:
        return _unresolved(
            request, analysis, effective, "dominance comparison backend failed"
        )
    if render_bytes > MAX_DOMINANCE_RENDER_BYTES:
        return _unresolved(request, analysis, effective, "dominance rendering bound exceeded")

    active_exclusions = {
        item
        for item in exclusions
        if _active(item, bounds) and (not integer or item.denominator == 1)
    }
    if numerator == 0:
        conditions = (
            "aggregate work is identically zero",
            *(f"{request.axis} != {_render(item)}" for item in sorted(active_exclusions)),
        )
        return DominanceAnalysisSuccess(
            analysis=analysis,
            axis=request.axis,
            axis_domain=request.variables[request.axis].domain,
            fixed={name: str(value) for name, value in request.fixed.items()},
            requested_range=request.range,
            effective_range=effective,
            shared_denominator=str(denominator),
            exclusions=tuple(
                DominanceExclusion(value=_render(item)) for item in sorted(active_exclusions)
            ),
            conditions=conditions,
            assumptions_used=_unique_uses(assumptions),
            dominance_status="complete",
        )
    active_boundaries = {item for item in boundaries if _active(item, bounds)}
    finite = active_boundaries | active_exclusions
    lower, upper, _, _ = bounds
    if lower is not None:
        finite.add(lower)
    if upper is not None:
        finite.add(upper)
    if len(finite) > MAX_DOMINANCE_POINTS:
        return _unresolved(
            request, analysis, effective, "dominance partition-point bound exceeded"
        )

    # A requested singleton that is a pole has no admissible points.
    if (
        lower is not None
        and upper is not None
        and lower == upper
        and lower in active_exclusions
    ):
        return DominanceAnalysisSuccess(
            analysis=analysis,
            axis=request.axis,
            axis_domain=request.variables[request.axis].domain,
            fixed={name: str(value) for name, value in request.fixed.items()},
            requested_range=request.range,
            effective_range=None,
            shared_denominator=str(denominator),
            terms=terms,
            dominance_status="empty",
        )

    try:
        cells, raw_cell_count = _cells(
            items,
            terms,
            sorted(active_boundaries | active_exclusions),
            active_exclusions,
            bounds,
            integer,
            request.axis,
        )
    except Exception:
        return _unresolved(request, analysis, effective, "dominance cell construction failed")
    if raw_cell_count > MAX_DOMINANCE_CELLS:
        return _unresolved(request, analysis, effective, "dominance cell bound exceeded")
    if pair_blockers:
        blocker = "; ".join(dict.fromkeys(pair_blockers))
        cells = [
            cell.model_copy(update={"dominant": (), "blockers": (blocker,)})
            for cell in cells
        ]
    if not cells:
        return DominanceAnalysisSuccess(
            analysis=analysis,
            axis=request.axis,
            axis_domain=request.variables[request.axis].domain,
            fixed={name: str(value) for name, value in request.fixed.items()},
            requested_range=request.range,
            effective_range=None,
            shared_denominator=str(denominator),
            terms=terms,
            dominance_status="empty",
        )

    active_ids = {item for cell in cells for item in cell.dominant}
    conditions = tuple(f"{request.axis} != {_render(item)}" for item in sorted(active_exclusions))
    result = DominanceAnalysisSuccess(
        analysis=analysis,
        axis=request.axis,
        axis_domain=request.variables[request.axis].domain,
        fixed={name: str(value) for name, value in request.fixed.items()},
        requested_range=request.range,
        effective_range=effective,
        shared_denominator=str(denominator),
        terms=terms,
        cells=tuple(cells),
        exclusions=tuple(
            DominanceExclusion(value=_render(item)) for item in sorted(active_exclusions)
        ),
        never_dominant=(
            ()
            if pair_blockers
            else tuple(term.id for term in terms if term.id not in active_ids)
        ),
        evidence=tuple(evidence),
        conditions=conditions,
        assumptions_used=_unique_uses(assumptions),
        dominance_status="unresolved" if pair_blockers else "complete",
    )
    supplement_bytes = len(
        result.model_dump_json(exclude={"analysis"}).encode("utf-8")
    )
    if supplement_bytes > MAX_DOMINANCE_SUPPLEMENT_BYTES:
        return _unresolved(
            request,
            analysis,
            effective,
            "dominance supplement bound exceeded",
            assumptions_used=_unique_uses(assumptions),
        )
    return result


def _winners(
    value: Fraction,
    items: list[tuple[int, Any]],
    terms: tuple[DominanceTerm, ...],
    axis: str,
) -> tuple[str, ...]:
    scores = dominance_magnitudes(items, value, axis)
    maximum = max(scores)
    return tuple(
        term.id for term, score in zip(terms, scores, strict=True) if score == maximum
    )


def _cells(
    items: list[tuple[int, Any]],
    terms: tuple[DominanceTerm, ...],
    cuts: list[Fraction],
    exclusions: set[Fraction],
    bounds: tuple[Fraction | None, Fraction | None, bool, bool],
    integer: bool,
    axis: str,
) -> tuple[list[Any], int]:
    if integer:
        raw = _integer_cells(items, terms, cuts, exclusions, bounds, axis)
        return _coalesce_integer(raw), len(raw)
    raw = _real_cells(items, terms, cuts, exclusions, bounds, axis)
    return _coalesce_real(raw), len(raw)


def _real_cells(
    items: list[tuple[int, Any]],
    terms: tuple[DominanceTerm, ...],
    cuts: list[Fraction],
    exclusions: set[Fraction],
    bounds: tuple[Fraction | None, Fraction | None, bool, bool],
    axis: str,
) -> list[Any]:
    lower, upper, lower_inclusive, upper_inclusive = bounds
    internal = [
        item
        for item in cuts
        if (lower is None or item > lower) and (upper is None or item < upper)
    ]
    boundaries: list[Fraction | None] = [lower, *internal, upper]
    if lower is None:
        boundaries[0] = None
    if upper is None:
        boundaries[-1] = None
    atoms: list[Any] = []
    for left, right in pairwise(boundaries):
        if left is not None and right is not None and left >= right:
            continue
        sample = (
            (left + right) / 2
            if left is not None and right is not None
            else left + 1
            if left is not None
            else right - 1
            if right is not None
            else Fraction(0)
        )
        atoms.append(
            DominanceIntervalCell(
                lower=_render(left),
                upper=_render(right, upper=True),
                lower_inclusive=False,
                upper_inclusive=False,
                dominant=_winners(sample, items, terms, axis),
            )
        )
        if right is not None and right != upper and right not in exclusions:
            atoms.append(
                DominancePointCell(
                    kind="real_point",
                    value=_render(right),
                    dominant=_winners(right, items, terms, axis),
                )
            )
    if lower is not None and lower_inclusive and lower not in exclusions:
        atoms.insert(
            0,
            DominancePointCell(
                kind="real_point",
                value=_render(lower),
                dominant=_winners(lower, items, terms, axis),
            ),
        )
    if upper is not None and upper_inclusive and upper not in exclusions:
        atoms.append(
            DominancePointCell(
                kind="real_point",
                value=_render(upper),
                dominant=_winners(upper, items, terms, axis),
            )
        )
    return atoms


def _coalesce_real(cells: list[Any]) -> list[Any]:
    result: list[Any] = []
    for cell in cells:
        if not result:
            result.append(cell)
            continue
        previous = result[-1]
        if (
            isinstance(previous, DominanceIntervalCell)
            and isinstance(cell, DominancePointCell)
            and cell.kind == "real_point"
            and previous.upper == cell.value
            and previous.dominant == cell.dominant
            and previous.blockers == cell.blockers
        ):
            result[-1] = previous.model_copy(update={"upper_inclusive": True})
            continue
        if (
            isinstance(previous, DominancePointCell)
            and previous.kind == "real_point"
            and isinstance(cell, DominanceIntervalCell)
            and previous.value == cell.lower
            and previous.dominant == cell.dominant
            and previous.blockers == cell.blockers
        ):
            result[-1] = cell.model_copy(update={"lower_inclusive": True})
            continue
        if (
            isinstance(previous, DominanceIntervalCell)
            and isinstance(cell, DominanceIntervalCell)
            and previous.upper == cell.lower
            and previous.upper_inclusive
            and previous.dominant == cell.dominant
            and previous.blockers == cell.blockers
        ):
            result[-1] = DominanceIntervalCell(
                lower=previous.lower,
                upper=cell.upper,
                lower_inclusive=previous.lower_inclusive,
                upper_inclusive=cell.upper_inclusive,
                dominant=previous.dominant,
                blockers=previous.blockers,
            )
            continue
        result.append(cell)
    return result


def _integer_cells(
    items: list[tuple[int, Any]],
    terms: tuple[DominanceTerm, ...],
    cuts: list[Fraction],
    exclusions: set[Fraction],
    bounds: tuple[Fraction | None, Fraction | None, bool, bool],
    axis: str,
) -> list[Any]:
    low, high = _integer_bounds(bounds)
    atoms: list[Any] = []
    current = low
    for cut in cuts:
        before = ceil(cut) - 1
        if high is not None:
            before = min(before, high)
        if current is None or current <= before:
            sample = before if current is None else current
            atoms.append(
                DominanceIntegerRangeCell(
                    lower="-oo" if current is None else str(current),
                    upper=str(before),
                    dominant=_winners(Fraction(sample), items, terms, axis),
                )
            )
        if cut.denominator == 1:
            integer_value = cut.numerator
            if (
                cut not in exclusions
                and (low is None or integer_value >= low)
                and (high is None or integer_value <= high)
            ):
                atoms.append(
                    DominancePointCell(
                        kind="integer_point",
                        value=str(integer_value),
                        dominant=_winners(cut, items, terms, axis),
                    )
                )
        current = floor(cut) + 1
        if low is not None:
            current = max(current, low)
        if high is not None and current > high:
            break
    if high is None or current is None or current <= high:
        sample = current if current is not None else high if high is not None else 0
        atoms.append(
            DominanceIntegerRangeCell(
                lower="-oo" if current is None else str(current),
                upper="oo" if high is None else str(high),
                dominant=_winners(Fraction(sample), items, terms, axis),
            )
        )
    return atoms


def _coalesce_integer(cells: list[Any]) -> list[Any]:
    result: list[Any] = []
    for cell in cells:
        if not result:
            result.append(cell)
            continue
        previous = result[-1]
        if previous.dominant != cell.dominant or previous.blockers != cell.blockers:
            result.append(cell)
            continue
        previous_lower = getattr(previous, "lower", getattr(previous, "value", None))
        previous_upper = getattr(previous, "upper", getattr(previous, "value", None))
        cell_lower = getattr(cell, "lower", getattr(cell, "value", None))
        cell_upper = getattr(cell, "upper", getattr(cell, "value", None))
        adjacent = previous_upper == "oo" or cell_lower == "-oo"
        if not adjacent and previous_upper is not None and cell_lower is not None:
            adjacent = int(cell_lower) == int(previous_upper) + 1
        if adjacent:
            result[-1] = DominanceIntegerRangeCell(
                lower=str(previous_lower),
                upper=str(cell_upper),
                dominant=previous.dominant,
                blockers=previous.blockers,
            )
        else:
            result.append(cell)
    return result
