# pyright: reportPrivateUsage=false
from fractions import Fraction
from itertools import combinations, pairwise
from typing import Annotated, Any, Literal, cast

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.contracts.common import (
    _NAME_PATTERN,
    MAX_ASSUMPTIONS,
    MAX_DEFINITIONS,
    MAX_EQUATIONS,
    MAX_FUNCTIONS,
    MAX_NAME_LENGTH,
    MAX_PRIMITIVE_COSTS,
    Assumption,
    DirectedDefinition,
    EquationRequest,
    ExactScenarioScalar,
    FormulaSyntax,
    FunctionDefinition,
    MathematicalDomain,
    PrimitiveCost,
    RelationshipUse,
    VariableDeclaration,
    _exact_scenario_scalar,
)
from py_science.formula.contracts.reports import AnalysisFailure, AnalysisSuccess
from py_science.formula.contracts.requests import AnalysisRequest
from py_science.formula.exact_values import parse_exact_scalar, render_exact
from pydantic import Field, ValidationInfo, field_validator, model_validator


class DominanceRange(StructuredModel):
    lower: str = "-oo"
    upper: str = "oo"
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    @model_validator(mode="before")
    @classmethod
    def default_infinite_endpoints_open(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        # Omitted infinite endpoints are canonical outward-open bounds.  Keep an
        # explicitly supplied inclusive infinity invalid rather than silently
        # rewriting it.
        result = dict(cast(dict[str, Any], value))
        if result.get("lower", "-oo") == "-oo" and "lower_inclusive" not in result:
            result["lower_inclusive"] = False
        if result.get("upper", "oo") == "oo" and "upper_inclusive" not in result:
            result["upper_inclusive"] = False
        return result

    @field_validator("lower", "upper", mode="before")
    @classmethod
    def canonical_bound(cls, value: object) -> str:
        text = str(value)
        if text in {"-oo", "oo"}:
            return text
        return _exact_scenario_scalar(value)

    @model_validator(mode="after")
    def ordered(self) -> "DominanceRange":
        if self.lower == "oo" or self.upper == "-oo":
            raise ValueError("range infinities must be outward-facing")
        if self.lower != "-oo" and self.upper != "oo":
            left, right = parse_exact_scalar(self.lower), parse_exact_scalar(self.upper)
            assert left is not None and right is not None
            comparison = left.numerator * right.denominator - right.numerator * left.denominator
            if comparison > 0:
                raise ValueError("range lower bound must not exceed upper bound")
        if self.lower == "-oo" and self.lower_inclusive:
            raise ValueError("infinite range bounds are open")
        if self.upper == "oo" and self.upper_inclusive:
            raise ValueError("infinite range bounds are open")
        return self


class DominanceAnalysisRequest(StructuredModel):
    operation: Literal["analyze_dominance"] = "analyze_dominance"
    syntax: FormulaSyntax
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    axis: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    fixed: dict[str, ExactScenarioScalar] = Field(default_factory=dict)
    range: DominanceRange | None = None
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)

    @field_validator("fixed", mode="before")
    @classmethod
    def canonical_fixed(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        raw = cast(dict[str, Any], value)
        return {name: _exact_scenario_scalar(item) for name, item in raw.items()}

    @model_validator(mode="after")
    def dominance_shape(self) -> "DominanceAnalysisRequest":
        # The ordinary model remains the single source of shared-shape rules.
        AnalysisRequest(
            syntax=self.syntax,
            expression=self.expression,
            equations=self.equations,
            variables=self.variables,
            functions=self.functions,
            primitive_costs=self.primitive_costs,
            assumptions=self.assumptions,
            definitions=self.definitions,
        )
        if self.axis == "oo" or self.axis not in self.variables:
            raise ValueError("axis must name one declared numeric variable")
        if (
            self.range is not None
            and self.range.lower == self.range.upper
            and not (self.range.lower_inclusive and self.range.upper_inclusive)
        ):
            raise ValueError("range bounds must define a nonempty interval")
        if self.axis in self.fixed:
            raise ValueError("axis cannot be fixed")
        unknown = set(self.fixed) - set(self.variables)
        if unknown:
            raise ValueError("fixed substitutions must name declared variables")
        defined = {item.variable for item in self.definitions}
        if self.axis in defined:
            raise ValueError("axis cannot be defined")
        if set(self.fixed) & defined:
            raise ValueError("fixed substitutions cannot conflict with definitions")
        for name, value in self.fixed.items():
            exact = parse_exact_scalar(str(value))
            assert exact is not None
            domain = self.variables[name].domain
            if domain.is_integer and exact.denominator != 1:
                raise ValueError(f"fixed.{name} must be integral for its declared domain")
            signed = Fraction(exact.numerator, exact.denominator)
            if (
                domain in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL}
                and signed <= 0
            ):
                raise ValueError(f"fixed.{name} must be positive for its declared domain")
            if (
                domain
                in {
                    MathematicalDomain.NONNEGATIVE_INTEGER,
                    MathematicalDomain.NONNEGATIVE_REAL,
                }
                and signed < 0
            ):
                raise ValueError(f"fixed.{name} must be nonnegative for its declared domain")
        return self

    def analysis_request(self) -> AnalysisRequest:
        return AnalysisRequest(
            syntax=self.syntax,
            expression=self.expression,
            equations=self.equations,
            variables=self.variables,
            functions=self.functions,
            primitive_costs=self.primitive_costs,
            assumptions=self.assumptions,
            definitions=self.definitions,
        )


class DominanceTerm(StructuredModel):
    id: str = Field(pattern=r"^power:(0|[1-9][0-9]*)$")
    power: int = Field(ge=0)
    coefficient: str
    expression: str

    @model_validator(mode="after")
    def canonical_id(self) -> "DominanceTerm":
        if self.id != f"power:{self.power}":
            raise ValueError("term id must correlate with canonical power")
        return self


class DominanceIntervalCell(StructuredModel):
    kind: Literal["real_interval"] = "real_interval"
    lower: str
    upper: str
    lower_inclusive: bool
    upper_inclusive: bool
    dominant: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def exact_bounds(self) -> "DominanceIntervalCell":
        checked = DominanceRange(
            lower=self.lower,
            upper=self.upper,
            lower_inclusive=self.lower_inclusive,
            upper_inclusive=self.upper_inclusive,
        )
        if checked.lower == checked.upper:
            raise ValueError("real dominance intervals must have positive width")
        return self


class DominancePointCell(StructuredModel):
    kind: Literal["real_point", "integer_point"]
    value: str
    dominant: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @field_validator("value")
    @classmethod
    def exact_point(cls, value: str, info: ValidationInfo) -> str:
        exact = parse_exact_scalar(value)
        if exact is None or render_exact(exact) != value:
            raise ValueError("dominance points must be canonical finite exact scalars")
        if info.data.get("kind") == "integer_point" and exact.denominator != 1:
            raise ValueError("integer dominance points must be integral")
        return value


class DominanceIntegerRangeCell(StructuredModel):
    kind: Literal["integer_range"] = "integer_range"
    lower: str
    upper: str
    dominant: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def integral_bounds(self) -> "DominanceIntegerRangeCell":
        for value in (self.lower, self.upper):
            if value in {"-oo", "oo"}:
                continue
            exact = parse_exact_scalar(value)
            if exact is None or exact.denominator != 1 or render_exact(exact) != value:
                raise ValueError("integer range bounds must be canonical integers or infinity")
        DominanceRange(
            lower=self.lower,
            upper=self.upper,
            lower_inclusive=self.lower != "-oo",
            upper_inclusive=self.upper != "oo",
        )
        return self


type DominanceCell = Annotated[
    DominanceIntervalCell | DominancePointCell | DominanceIntegerRangeCell,
    Field(discriminator="kind"),
]


class DominanceExclusion(StructuredModel):
    value: str
    reason: Literal["pole"] = "pole"

    @field_validator("value")
    @classmethod
    def exact_value(cls, value: str) -> str:
        exact = parse_exact_scalar(value)
        if exact is None or render_exact(exact) != value:
            raise ValueError("dominance exclusions must be canonical finite exact values")
        return value


class DominanceEvidence(StructuredModel):
    pair: tuple[str, str]
    difference: str = Field(min_length=1, max_length=262_144)
    sign: Literal[-1, 0, 1] | None = None
    roots: tuple[str, ...] = Field(default=(), max_length=256)


def _dominance_exact_sort_key(value: str) -> Fraction:
    exact = parse_exact_scalar(value)
    assert exact is not None
    return Fraction(exact.numerator, exact.denominator)


def _dominance_cell_bounds(
    cell: DominanceCell,
) -> tuple[Fraction | None, Fraction | None, bool, bool]:
    if isinstance(cell, DominancePointCell):
        point = _dominance_exact_sort_key(cell.value)
        return point, point, True, True
    lower = None if cell.lower == "-oo" else _dominance_exact_sort_key(cell.lower)
    upper = None if cell.upper == "oo" else _dominance_exact_sort_key(cell.upper)
    if isinstance(cell, DominanceIntegerRangeCell):
        return lower, upper, lower is not None, upper is not None
    return lower, upper, cell.lower_inclusive, cell.upper_inclusive


def _validate_dominance_cell_order(
    cells: tuple[DominanceCell, ...], exclusions: tuple[str, ...]
) -> None:
    previous: tuple[Fraction | None, bool] | None = None
    for cell in cells:
        lower, upper, lower_inclusive, upper_inclusive = _dominance_cell_bounds(cell)
        if previous is not None:
            previous_upper, previous_inclusive = previous
            if previous_upper is None:
                raise ValueError("unbounded dominance cell must be last")
            if (
                lower is None
                or lower < previous_upper
                or (lower == previous_upper and lower_inclusive and previous_inclusive)
            ):
                raise ValueError("dominance cells must be ordered and disjoint")
        previous = (upper, upper_inclusive)
    for value in exclusions:
        point = _dominance_exact_sort_key(value)
        for cell in cells:
            lower, upper, lower_inclusive, upper_inclusive = _dominance_cell_bounds(cell)
            inside = (lower is None or point > lower or (point == lower and lower_inclusive)) and (
                upper is None or point < upper or (point == upper and upper_inclusive)
            )
            if inside:
                raise ValueError("dominance exclusions cannot be covered by cells")


def _range_bounds(
    value: DominanceRange,
) -> tuple[Fraction | None, Fraction | None, bool, bool]:
    lower = None if value.lower == "-oo" else _dominance_exact_sort_key(value.lower)
    upper = None if value.upper == "oo" else _dominance_exact_sort_key(value.upper)
    return lower, upper, value.lower_inclusive, value.upper_inclusive


def _dominance_bounds_within(
    inner: tuple[Fraction | None, Fraction | None, bool, bool],
    outer: tuple[Fraction | None, Fraction | None, bool, bool],
) -> bool:
    inner_lower, inner_upper, inner_lower_inclusive, inner_upper_inclusive = inner
    outer_lower, outer_upper, outer_lower_inclusive, outer_upper_inclusive = outer
    lower_ok = outer_lower is None or (
        inner_lower is not None
        and (
            inner_lower > outer_lower
            or (inner_lower == outer_lower and (outer_lower_inclusive or not inner_lower_inclusive))
        )
    )
    upper_ok = outer_upper is None or (
        inner_upper is not None
        and (
            inner_upper < outer_upper
            or (inner_upper == outer_upper and (outer_upper_inclusive or not inner_upper_inclusive))
        )
    )
    return lower_ok and upper_ok


def _validate_complete_dominance_coverage(
    cells: tuple[DominanceCell, ...],
    exclusions: tuple[str, ...],
    effective: DominanceRange,
    *,
    integer: bool,
) -> None:
    if not cells:
        raise ValueError("complete nonzero dominance requires domain coverage")
    excluded = {_dominance_exact_sort_key(item) for item in exclusions}
    effective_lower, effective_upper, lower_inclusive, upper_inclusive = _range_bounds(effective)
    bounds = [_dominance_cell_bounds(cell) for cell in cells]
    first_lower, _, first_inclusive, _ = bounds[0]
    _, last_upper, _, last_inclusive = bounds[-1]
    if integer:
        low = (
            None
            if effective_lower is None
            else int(effective_lower.__ceil__())
            if lower_inclusive
            else int(effective_lower.__floor__()) + 1
        )
        high = (
            None
            if effective_upper is None
            else int(effective_upper.__floor__())
            if upper_inclusive
            else int(effective_upper.__ceil__()) - 1
        )
        if first_lower != (None if low is None else Fraction(low)):
            raise ValueError("complete integer dominance must start at its active domain")
        if last_upper != (None if high is None else Fraction(high)):
            raise ValueError("complete integer dominance must end at its active domain")
        for previous, current in pairwise(bounds):
            previous_upper, current_lower = previous[1], current[0]
            if previous_upper is None or current_lower is None:
                raise ValueError("unbounded integer dominance cells are misplaced")
            gap_start = int(previous_upper) + 1
            gap_end = int(current_lower) - 1
            if (
                gap_start <= gap_end
                and {Fraction(item) for item in range(gap_start, gap_end + 1)} - excluded
            ):
                raise ValueError("complete integer dominance has an uncovered lattice gap")
        return
    if first_lower != effective_lower or last_upper != effective_upper:
        raise ValueError("complete real dominance must match its active-domain bounds")
    if lower_inclusive and not first_inclusive and effective_lower not in excluded:
        raise ValueError("complete real dominance omits its inclusive lower endpoint")
    if upper_inclusive and not last_inclusive and effective_upper not in excluded:
        raise ValueError("complete real dominance omits its inclusive upper endpoint")
    for previous, current in pairwise(bounds):
        previous_upper, previous_inclusive = previous[1], previous[3]
        current_lower, current_inclusive = current[0], current[2]
        if previous_upper != current_lower:
            raise ValueError("complete real dominance has an uncovered interval")
        if not previous_inclusive and not current_inclusive and previous_upper not in excluded:
            raise ValueError("complete real dominance has an uncovered point")


class DominanceAnalysisSuccess(StructuredModel):
    kind: Literal["dominance_analysis"] = "dominance_analysis"
    status: Literal["success"] = "success"
    analysis: AnalysisSuccess
    metric: Literal["aggregate_abstract_work"] = "aggregate_abstract_work"
    axis: str
    axis_domain: MathematicalDomain
    fixed: dict[str, str] = Field(default_factory=dict)
    requested_range: DominanceRange | None = None
    effective_range: DominanceRange | None
    shared_denominator: str | None = None
    terms: tuple[DominanceTerm, ...] = Field(default=(), max_length=16)
    cells: tuple[DominanceCell, ...] = Field(default=(), max_length=513)
    exclusions: tuple[DominanceExclusion, ...] = Field(default=(), max_length=256)
    never_dominant: tuple[str, ...] = Field(default=(), max_length=16)
    conditions: tuple[str, ...] = ()
    assumptions_used: tuple[RelationshipUse, ...] = ()
    blockers: tuple[str, ...] = ()
    evidence: tuple[DominanceEvidence, ...] = Field(default=(), max_length=120)
    dominance_status: Literal["complete", "unresolved", "empty"]

    @model_validator(mode="after")
    def truth_table(self) -> "DominanceAnalysisSuccess":
        ids = tuple(term.id for term in self.terms)
        if ids != tuple(sorted(ids, key=lambda item: int(item[6:]), reverse=True)) or len(
            ids
        ) != len(set(ids)):
            raise ValueError("terms must be unique and descending by power")
        if len(self.fixed) != len(set(self.fixed)):
            raise ValueError("fixed substitutions must be unique")
        if self.axis in self.fixed:
            raise ValueError("axis cannot appear in fixed substitutions")
        for value in self.fixed.values():
            exact = parse_exact_scalar(value)
            if exact is None or render_exact(exact) != value:
                raise ValueError("fixed substitutions must be canonical exact scalars")
        if self.dominance_status == "empty":
            if self.effective_range is not None:
                raise ValueError("empty dominance has no effective range")
            if self.cells or self.exclusions or self.blockers or self.never_dominant:
                raise ValueError("empty dominance has no cells, exclusions, blockers, or claims")
        elif self.effective_range is None:
            raise ValueError("nonempty dominance requires an effective range")
        if self.effective_range is not None:
            (
                effective_lower,
                effective_upper,
                effective_lower_inclusive,
                effective_upper_inclusive,
            ) = _range_bounds(self.effective_range)
            domain_lower = (
                Fraction(0)
                if self.axis_domain
                in {
                    MathematicalDomain.POSITIVE_INTEGER,
                    MathematicalDomain.POSITIVE_REAL,
                    MathematicalDomain.NONNEGATIVE_INTEGER,
                    MathematicalDomain.NONNEGATIVE_REAL,
                }
                else None
            )
            domain_lower_inclusive = self.axis_domain in {
                MathematicalDomain.NONNEGATIVE_INTEGER,
                MathematicalDomain.NONNEGATIVE_REAL,
            }
            if domain_lower is not None and (
                effective_lower is None
                or effective_lower < domain_lower
                or (
                    effective_lower == domain_lower
                    and effective_lower_inclusive
                    and not domain_lower_inclusive
                )
            ):
                raise ValueError("effective range must lie within the axis domain")
            if self.requested_range is not None:
                (
                    requested_lower,
                    requested_upper,
                    requested_lower_inclusive,
                    requested_upper_inclusive,
                ) = _range_bounds(self.requested_range)
                if (
                    requested_lower is not None
                    and (
                        effective_lower is None
                        or effective_lower < requested_lower
                        or (
                            effective_lower == requested_lower
                            and effective_lower_inclusive
                            and not requested_lower_inclusive
                        )
                    )
                ) or (
                    requested_upper is not None
                    and (
                        effective_upper is None
                        or effective_upper > requested_upper
                        or (
                            effective_upper == requested_upper
                            and effective_upper_inclusive
                            and not requested_upper_inclusive
                        )
                    )
                ):
                    raise ValueError("effective range must lie within requested range")
        if self.dominance_status == "complete":
            if self.blockers or any(cell.blockers for cell in self.cells):
                raise ValueError("complete dominance has no blockers")
            if not self.terms:
                if (
                    self.cells
                    or self.never_dominant
                    or self.shared_denominator is None
                    or "aggregate work is identically zero" not in self.conditions
                ):
                    raise ValueError("empty complete decomposition is only zero work")
            elif not self.cells or self.shared_denominator is None:
                raise ValueError("complete decomposition requires terms, denominator, and cells")
        elif self.dominance_status == "unresolved":
            if not self.blockers and not any(cell.blockers for cell in self.cells):
                raise ValueError("unresolved dominance requires blockers or unresolved cells")
            if self.never_dominant:
                raise ValueError("unresolved dominance cannot claim never-dominant terms")
            if not self.terms and (self.shared_denominator is not None or self.cells):
                raise ValueError("pre-decomposition unresolved dominance has no decomposition")
        if len(self.never_dominant) != len(set(self.never_dominant)) or set(
            self.never_dominant
        ) - set(ids):
            raise ValueError("never-dominant terms must be unique reported terms")
        for cell in self.cells:
            if self.axis_domain.is_integer != (cell.kind.startswith("integer")):
                raise ValueError("dominance cell kind must match the axis domain")
            if cell.blockers == () and not cell.dominant:
                raise ValueError("complete dominance cells require dominant terms")
            if cell.blockers and cell.dominant:
                raise ValueError("unresolved dominance cells cannot claim dominant terms")
            if len(cell.dominant) != len(set(cell.dominant)) or any(
                item not in ids for item in cell.dominant
            ):
                raise ValueError("cell terms must be unique reported ids")
            if tuple(item for item in ids if item in cell.dominant) != cell.dominant:
                raise ValueError("dominant ids must follow canonical term order")
        active = {item for cell in self.cells for item in cell.dominant}
        if (
            self.dominance_status == "complete"
            and self.terms
            and tuple(item for item in ids if item not in active) != self.never_dominant
        ):
            raise ValueError("never-dominant ids must be the proved complement")
        expected_pairs = tuple(combinations(ids, 2))
        pairs = tuple(item.pair for item in self.evidence)
        if len(pairs) != len(set(pairs)) or any(pair not in expected_pairs for pair in pairs):
            raise ValueError("dominance evidence pairs must be unique reported term pairs")
        if self.dominance_status == "complete" and self.terms and pairs != expected_pairs:
            raise ValueError("complete dominance requires every pair in canonical order")
        exclusion_values = tuple(item.value for item in self.exclusions)
        if exclusion_values != tuple(sorted(set(exclusion_values), key=_dominance_exact_sort_key)):
            raise ValueError("dominance exclusions must be unique and ordered")
        if self.axis_domain.is_integer and any(
            _dominance_exact_sort_key(item).denominator != 1 for item in exclusion_values
        ):
            raise ValueError("integer dominance exclusions must be integral")
        _validate_dominance_cell_order(self.cells, exclusion_values)
        if self.effective_range is not None:
            effective_bounds = _range_bounds(self.effective_range)
            if any(
                not _dominance_bounds_within(_dominance_cell_bounds(cell), effective_bounds)
                for cell in self.cells
            ) or any(
                not _dominance_bounds_within((point, point, True, True), effective_bounds)
                for point in map(_dominance_exact_sort_key, exclusion_values)
            ):
                raise ValueError(
                    "dominance cells and exclusions must lie within the effective range"
                )
        if any(f"{self.axis} != {value}" not in self.conditions for value in exclusion_values):
            raise ValueError("dominance exclusions require matching conditions")
        if self.dominance_status == "complete" and self.terms:
            assert self.effective_range is not None
            _validate_complete_dominance_coverage(
                self.cells,
                exclusion_values,
                self.effective_range,
                integer=self.axis_domain.is_integer,
            )
        return self


type DominanceAnalysisOutcome = Annotated[
    DominanceAnalysisSuccess | AnalysisFailure, Field(discriminator="status")
]
