# ruff: noqa: E501
import re
from collections.abc import Iterable
from enum import StrEnum
from fractions import Fraction
from itertools import combinations, pairwise
from typing import Annotated, Any, Literal, cast

from py_science.formula.exact_values import parse_exact_scalar, render_exact
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

MAX_NAME_LENGTH = 128
MAX_FORMULA_BYTES = 65_536
MAX_EQUATIONS = 128
MAX_FUNCTIONS = 128
MAX_VARIABLES = 256
MAX_PRIMITIVE_COSTS = 128
MAX_ASSUMPTIONS = 128
MAX_DEFINITIONS = 128
MAX_SCENARIOS = 64
MAX_TREATMENTS_PER_SCENARIO = 64
MAX_CHOICES_PER_VARIABLE = 32
MAX_GENERATED_SCENARIO_RESULTS = 256
MAX_SCENARIO_INTEGER_BITS = 3_402
type ExactScenarioScalar = str | int
MAX_DOMAINS_PER_EQUATION = 32
MAX_CONSTRAINTS_PER_EQUATION = 32
MAX_PARAMETERS = 32
_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*$"


class StructuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FormulaSyntax(StrEnum):
    SYMPY = "sympy"


class MathematicalDomain(StrEnum):
    INTEGER = "integer"
    NONNEGATIVE_INTEGER = "nonnegative_integer"
    POSITIVE_INTEGER = "positive_integer"
    REAL = "real"
    POSITIVE_REAL = "positive_real"
    NONNEGATIVE_REAL = "nonnegative_real"

    @property
    def is_integer(self) -> bool:
        return self in {
            MathematicalDomain.INTEGER,
            MathematicalDomain.NONNEGATIVE_INTEGER,
            MathematicalDomain.POSITIVE_INTEGER,
        }


class AnalysisErrorCode(StrEnum):
    MALFORMED_SYNTAX = "malformed_syntax"
    UNSUPPORTED_CONSTRUCT = "unsupported_construct"
    EXPRESSION_TOO_COMPLEX = "expression_too_complex"
    NORMALIZATION_FAILED = "normalization_failed"
    INVALID_SYSTEM = "invalid_system"


class IndexDomain(StructuredModel):
    lower: str
    upper: str


class VariableDeclaration(StructuredModel):
    domain: MathematicalDomain


class Assumption(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    relationship: str


class DirectedDefinition(StructuredModel):
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable


def _exact_scenario_scalar(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(
            "scenario scalar must be an exact scalar string or JavaScript-safe integer"
        )
    if isinstance(value, int) and abs(value) > 9_007_199_254_740_991:
        raise ValueError("numeric scenario scalar must be a JavaScript-safe integer")
    parsed = parse_exact_scalar(str(value))
    if parsed is None:
        raise ValueError("scenario scalar must use the exact scalar grammar")
    return render_exact(parsed)


class IntervalBound(StructuredModel):
    lower: ExactScenarioScalar
    upper: ExactScenarioScalar
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    @field_validator("lower", "upper", mode="before")
    @classmethod
    def canonical_scalar(cls, value: object) -> str:
        return _exact_scenario_scalar(value)

    @model_validator(mode="after")
    def validate_order(self) -> "IntervalBound":
        lower = parse_exact_scalar(str(self.lower))
        upper = parse_exact_scalar(str(self.upper))
        assert lower is not None and upper is not None
        if (lower.numerator * upper.denominator > upper.numerator * lower.denominator) or (
            lower.numerator * upper.denominator == upper.numerator * lower.denominator
            and not (self.lower_inclusive and self.upper_inclusive)
        ):
            raise ValueError("interval bounds must define a nonempty interval")
        return self


class Scenario(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    fixed: dict[str, ExactScenarioScalar] = Field(default_factory=dict)
    choices: dict[str, tuple[ExactScenarioScalar, ...]] = Field(default_factory=dict)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    asymptotic: tuple[str, ...] = ()
    bounds: dict[str, IntervalBound] = Field(default_factory=dict)

    @field_validator("fixed", mode="before")
    @classmethod
    def canonical_fixed(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        raw = cast(dict[str, Any], values)
        return {name: _exact_scenario_scalar(value) for name, value in raw.items()}

    @field_validator("choices", mode="before")
    @classmethod
    def canonical_choices(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        raw = cast(dict[str, Any], values)
        return {
            name: tuple(_exact_scenario_scalar(value) for value in choices)
            for name, choices in raw.items()
        }

    @model_validator(mode="after")
    def validate_treatments(self) -> "Scenario":
        populations = (
            len(self.fixed)
            + len(self.choices)
            + len(self.definitions)
            + len(self.asymptotic)
            + len(self.bounds)
        )
        if populations > MAX_TREATMENTS_PER_SCENARIO:
            raise ValueError("scenario treatment collection exceeds its bound")
        names = [
            *self.fixed,
            *self.choices,
            *(item.variable for item in self.definitions),
            *self.asymptotic,
            *self.bounds,
        ]
        if any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in names
        ):
            raise ValueError("scenario variable names must be ordinary identifiers")
        if len(names) != len(set(names)):
            raise ValueError("a scenario variable may have only one treatment")
        if any(
            not values or len(values) > MAX_CHOICES_PER_VARIABLE for values in self.choices.values()
        ):
            raise ValueError("finite choices must be nonempty and within their bound")
        if any(len(values) != len(set(values)) for values in self.choices.values()):
            raise ValueError("finite choices must be unique")
        generated = 1
        for values in self.choices.values():
            generated *= len(values)
            if generated > MAX_GENERATED_SCENARIO_RESULTS:
                raise ValueError("scenario generated-result population exceeds its bound")
        return self


class DomainConstraint(StructuredModel):
    """One named, equation-local relationship tightening an output index."""

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    relationship: str = Field(min_length=1, max_length=262_144)


class EquationRequest(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str
    domains: dict[str, IndexDomain] = Field(default_factory=dict)
    constraints: tuple[DomainConstraint, ...] = Field(
        default=(), max_length=MAX_CONSTRAINTS_PER_EQUATION
    )

    @field_validator("constraints")
    @classmethod
    def validate_constraint_names(
        cls, constraints: tuple[DomainConstraint, ...]
    ) -> tuple[DomainConstraint, ...]:
        names: set[str] = set()
        for position, constraint in enumerate(constraints):
            if constraint.name in names:
                raise ValidationError.from_exception_data(
                    cls.__name__,
                    [
                        {
                            "type": "value_error",
                            "loc": (position, "name"),
                            "input": constraint.name,
                            "ctx": {
                                "error": ValueError("equation constraint names must be unique")
                            },
                        }
                    ],
                )
            names.add(constraint.name)
        return constraints

    @model_validator(mode="after")
    def validate_domains(self) -> "EquationRequest":
        if len(self.domains) > MAX_DOMAINS_PER_EQUATION:
            raise ValueError("equation domain collection exceeds its bound")
        if any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in self.domains
        ):
            raise ValueError("equation domain names must be ordinary identifiers")
        return self


class FunctionDefinition(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    parameters: tuple[str, ...] = Field(max_length=MAX_PARAMETERS)
    body: str

    @model_validator(mode="after")
    def validate_parameters(self) -> "FunctionDefinition":
        if self.name in {"oo", "Let"}:
            raise ValueError(f"{self.name} is reserved for mathematical syntax")
        _validate_parameters(self.parameters)
        return self


class PrimitiveCost(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    parameters: tuple[str, ...] = Field(max_length=MAX_PARAMETERS)
    work: str

    @model_validator(mode="after")
    def validate_parameters(self) -> "PrimitiveCost":
        if self.name in {"oo", "Let"}:
            raise ValueError(f"{self.name} is reserved for mathematical syntax")
        _validate_parameters(self.parameters)
        return self


def _validate_parameters(parameters: tuple[str, ...]) -> None:
    if len(set(parameters)) != len(parameters):
        raise ValueError("function parameters must be unique")
    if any(
        parameter == "oo"
        or len(parameter) > MAX_NAME_LENGTH
        or re.fullmatch(_NAME_PATTERN, parameter) is None
        for parameter in parameters
    ):
        raise ValueError("function parameters must be ordinary identifiers")


class EquationTarget(StructuredModel):
    kind: Literal["equation"] = "equation"
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("name")
    @classmethod
    def ordinary_name(cls, name: str) -> str:
        if name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return name


class ExpressionTarget(StructuredModel):
    kind: Literal["expression"] = "expression"


class DerivedTarget(StructuredModel):
    kind: Literal["derived"] = "derived"
    query: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("query")
    @classmethod
    def ordinary_name(cls, query: str) -> str:
        if query == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return query


class VariablePropertyCheck(StructuredModel):
    kind: Literal["valid_domain", "singularities", "monotonicity"]
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("variable")
    @classmethod
    def ordinary_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable


class SignPropertyCheck(StructuredModel):
    kind: Literal["sign"] = "sign"


type PropertyCheck = Annotated[
    VariablePropertyCheck | SignPropertyCheck, Field(discriminator="kind")
]


class QueryBase(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: EquationTarget | DerivedTarget | None = None

    @field_validator("name")
    @classmethod
    def ordinary_name(cls, name: str) -> str:
        if name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return name


class EquivalenceQuery(QueryBase):
    kind: Literal["equivalence"] = "equivalence"
    comparison: str = Field(min_length=1, max_length=262_144)


class ClosedFormQuery(QueryBase):
    kind: Literal["closed_form"] = "closed_form"


class PropertiesQuery(QueryBase):
    kind: Literal["properties"] = "properties"
    checks: tuple[PropertyCheck, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def unique_checks(self) -> "PropertiesQuery":
        if len({item.model_dump_json() for item in self.checks}) != len(self.checks):
            raise ValueError("property checks must be unique")
        return self


class LimitQuery(QueryBase):
    kind: Literal["limit"] = "limit"
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("variable")
    @classmethod
    def ordinary_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable

    point: str | int
    direction: Literal["left", "right", "both"] | None = None

    @model_validator(mode="after")
    def valid_point(self) -> "LimitQuery":
        if isinstance(self.point, int) and abs(self.point) > 9_007_199_254_740_991:
            raise ValueError("numeric point must be a JavaScript-safe integer")
        if str(self.point) not in {"oo", "-oo"} and parse_exact_scalar(str(self.point)) is None:
            raise ValueError("point must be an exact scalar or infinity")
        if (str(self.point) in {"oo", "-oo"}) == (self.direction is not None):
            raise ValueError("finite points require direction and infinity forbids it")
        return self


class AsymptoticQuery(QueryBase):
    kind: Literal["asymptotic"] = "asymptotic"
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("variable")
    @classmethod
    def ordinary_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable

    point: str | int
    direction: Literal["left", "right", "both"] | None = None
    order: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def valid_point(self) -> "AsymptoticQuery":
        if isinstance(self.point, int) and abs(self.point) > 9_007_199_254_740_991:
            raise ValueError("numeric point must be a JavaScript-safe integer")
        if str(self.point) not in {"oo", "-oo"} and parse_exact_scalar(str(self.point)) is None:
            raise ValueError("point must be an exact scalar or infinity")
        if (str(self.point) in {"oo", "-oo"}) == (self.direction is not None):
            raise ValueError("finite points require direction and infinity forbids it")
        return self


QueryRequest = Annotated[
    EquivalenceQuery | ClosedFormQuery | PropertiesQuery | LimitQuery | AsymptoticQuery,
    Field(discriminator="kind"),
]


type ResolvedTarget = Annotated[
    ExpressionTarget | EquationTarget | DerivedTarget, Field(discriminator="kind")
]


class DerivedCandidate(StructuredModel):
    interpretation: "Interpretation"
    operation_counts: "OperationCounts"


class IdentityEvidence(StructuredModel):
    kind: Literal["identity"] = "identity"
    statement: str = Field(min_length=1, max_length=4096)


class CounterexampleEvidence(StructuredModel):
    kind: Literal["counterexample"] = "counterexample"
    substitutions: dict[str, str] = Field(max_length=256)
    target_value: str = Field(min_length=1, max_length=4096)
    comparison_value: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def canonical_substitutions(self) -> "CounterexampleEvidence":
        if any(
            len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None or name == "oo"
            for name in self.substitutions
        ):
            raise ValueError("counterexample substitution names must be ordinary identifiers")
        parsed = (parse_exact_scalar(value) for value in self.substitutions.values())
        if any(
            item is None or render_exact(item) != value
            for item, value in zip(parsed, self.substitutions.values(), strict=True)
        ):
            raise ValueError("counterexample substitutions must be canonical exact scalars")
        for value in (self.target_value, self.comparison_value):
            exact = parse_exact_scalar(value)
            if exact is None or render_exact(exact) != value:
                raise ValueError("counterexample values must be canonical exact scalars")
        return self


class ClosedFormEvidence(StructuredModel):
    kind: Literal["closed_form"] = "closed_form"
    verification: Literal["finite_antidifference", "infinite_partial_sum"]
    statement: str = Field(min_length=1, max_length=4096)


class PropertyEvidence(StructuredModel):
    kind: Literal["property"] = "property"
    value: str = Field(min_length=1, max_length=4096)
    intervals: tuple[str, ...] = Field(default=(), max_length=256)


type BoundedQueryText = Annotated[str, Field(min_length=1, max_length=4096)]


class LimitEvidence(StructuredModel):
    kind: Literal["limit"] = "limit"
    exists: bool
    value: BoundedQueryText | None
    left: BoundedQueryText | None
    right: BoundedQueryText | None


class AsymptoticRemainder(StructuredModel):
    local_parameter: str = Field(min_length=1, max_length=4096)
    exponent: int
    normalized_big_o: str = Field(min_length=1, max_length=4096)


class AsymptoticEvidence(StructuredModel):
    kind: Literal["asymptotic"] = "asymptotic"
    statement: str = Field(min_length=1, max_length=4096)
    remainder: AsymptoticRemainder | None


type QueryEvidence = Annotated[
    IdentityEvidence
    | CounterexampleEvidence
    | ClosedFormEvidence
    | PropertyEvidence
    | LimitEvidence
    | AsymptoticEvidence,
    Field(discriminator="kind"),
]


class QueryAnswer(StructuredModel):
    check: PropertyCheck | None = None
    conclusion: Literal[
        "proved", "proved_under_assumptions", "disproved", "unresolved", "inapplicable"
    ]
    conditions: tuple[str, ...] = Field(default=(), max_length=256)
    assumptions_used: tuple["RelationshipUse", ...] = Field(default=(), max_length=128)
    relevant_unsupported_assumptions: tuple[str, ...] = Field(default=(), max_length=128)
    blockers: tuple[str, ...] = Field(default=(), max_length=128)
    evidence: QueryEvidence | None = None
    derived_candidates: tuple[DerivedCandidate, ...] = Field(default=(), max_length=32)
    constraint_uses: tuple["ConstraintUse", ...] = ()

    @model_validator(mode="after")
    def terminal_shape(self) -> "QueryAnswer":
        bounded = (*self.conditions, *self.relevant_unsupported_assumptions, *self.blockers)
        if any(not value or len(value) > 4096 for value in bounded):
            raise ValueError("query qualification strings must be nonempty and bounded")
        if self.conclusion in {"unresolved", "inapplicable"} and self.derived_candidates:
            raise ValueError("unresolved and inapplicable answers cannot carry candidates")
        return self


class QueryResultCommon(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: ResolvedTarget

    @field_validator("name")
    @classmethod
    def ordinary_name(cls, name: str) -> str:
        if name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return name

    normalized_target: "Interpretation | None"
    summary: str = Field(min_length=1, max_length=4096)
    answers: tuple[QueryAnswer, ...]

    @model_validator(mode="after")
    def derived_target_nullability(self) -> "QueryResultCommon":
        unavailable = False
        if (
            isinstance(self.target, DerivedTarget)
            and self.answers
            and all(answer.conclusion == "inapplicable" for answer in self.answers)
        ):
            prefix = f"derived target source {self.target.query} concluded "
            conclusions = tuple(
                tuple(
                    blocker.removeprefix(prefix)
                    for blocker in answer.blockers
                    if blocker.startswith(prefix)
                )
                for answer in self.answers
            )
            unavailable = (
                all(len(items) == 1 for items in conclusions)
                and len({items[0] for items in conclusions}) == 1
                and conclusions[0][0]
                in {
                    "proved",
                    "proved_under_assumptions",
                    "disproved",
                    "unresolved",
                    "inapplicable",
                }
            )
        if (self.normalized_target is None) != unavailable:
            raise ValueError("normalized target is null only for an unavailable derived target")
        return self


class EquivalenceResult(QueryResultCommon):
    kind: Literal["equivalence"] = "equivalence"

    @model_validator(mode="after")
    def exact_answer(self) -> "EquivalenceResult":
        _validate_query_answers(self.answers, None, {"identity", "counterexample"})
        return self


class ClosedFormResult(QueryResultCommon):
    kind: Literal["closed_form"] = "closed_form"

    @model_validator(mode="after")
    def exact_answer(self) -> "ClosedFormResult":
        _validate_query_answers(self.answers, None, {"closed_form"})
        return self


class PropertiesResult(QueryResultCommon):
    kind: Literal["properties"] = "properties"

    @model_validator(mode="after")
    def property_answers(self) -> "PropertiesResult":
        if not self.answers or any(answer.check is None for answer in self.answers):
            raise ValueError("properties results require checked answers")
        checks = tuple(
            answer.check.model_dump_json() for answer in self.answers if answer.check is not None
        )
        if len(checks) != len(set(checks)):
            raise ValueError("properties result checks must be unique")
        if any(
            answer.evidence is not None and answer.evidence.kind != "property"
            for answer in self.answers
        ):
            raise ValueError("properties results require property evidence")
        return self


class LimitResult(QueryResultCommon):
    kind: Literal["limit"] = "limit"

    @model_validator(mode="after")
    def exact_answer(self) -> "LimitResult":
        _validate_query_answers(self.answers, None, {"limit"})
        return self


class AsymptoticResult(QueryResultCommon):
    kind: Literal["asymptotic"] = "asymptotic"

    @model_validator(mode="after")
    def exact_answer(self) -> "AsymptoticResult":
        _validate_query_answers(self.answers, None, {"asymptotic"})
        return self


def _validate_query_answers(
    answers: tuple[QueryAnswer, ...], check: None, evidence_kinds: set[str]
) -> None:
    if len(answers) != 1 or answers[0].check is not check:
        raise ValueError("query result requires exactly one unchecked answer")
    if answers[0].evidence is not None and answers[0].evidence.kind not in evidence_kinds:
        raise ValueError("query evidence kind does not match result kind")


type QueryResult = Annotated[
    EquivalenceResult | ClosedFormResult | PropertiesResult | LimitResult | AsymptoticResult,
    Field(discriminator="kind"),
]


class OptimizationConfig(StructuredModel):
    """Bounded, informational advice requested only for ordinary analysis."""

    max_suggestions: int = Field(default=3, ge=0, le=16)


class AnalysisRequest(StructuredModel):
    syntax: FormulaSyntax
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    scenarios: tuple[Scenario, ...] = Field(default=(), max_length=MAX_SCENARIOS)
    queries: tuple[QueryRequest, ...] = Field(default=(), max_length=32)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)

    @model_validator(mode="after")
    def validate_request(self) -> "AnalysisRequest":
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        if len(self.variables) > MAX_VARIABLES:
            raise ValueError("variable collection exceeds its bound")
        if any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in self.variables
        ):
            raise ValueError("variable names must be ordinary identifiers")
        _require_unique((equation.name for equation in self.equations), "equation names")
        _require_unique((function.name for function in self.functions), "function names")
        _require_unique((cost.name for cost in self.primitive_costs), "primitive cost names")
        definition_names = {function.name for function in self.functions}
        cost_names = {cost.name for cost in self.primitive_costs}
        if definition_names & cost_names:
            raise ValueError("a function cannot have both a definition and primitive work")
        callable_names = definition_names | cost_names
        if {"Eq", "Sum", "Max", "cardinality", "oo"} & callable_names or any(
            name.startswith("C_") for name in callable_names
        ):
            raise ValueError(
                "Eq, Sum, Max, cardinality, and C_ names are reserved mathematical constructs"
            )
        _require_unique((item.name for item in self.assumptions), "assumption names")
        _require_unique(
            (item.variable for item in self.definitions), "directed definition variables"
        )
        _require_unique((item.name for item in self.scenarios), "scenario names")
        _require_unique((item.name for item in self.queries), "query names")
        if (
            sum(
                len(item.comparison.encode("utf-8")) if isinstance(item, EquivalenceQuery) else 0
                for item in self.queries
            )
            > MAX_FORMULA_BYTES
        ):
            raise ValueError("query source exceeds its aggregate bound")
        for position, item in enumerate(self.queries):
            if self.expression is not None and isinstance(item.target, EquationTarget):
                raise ValueError("single-expression queries must omit equation target")
            if self.equations and item.target is None:
                raise ValueError("system queries require a named equation target")
            if isinstance(item.target, DerivedTarget):
                if not isinstance(
                    item, (EquivalenceQuery, PropertiesQuery, LimitQuery, AsymptoticQuery)
                ):
                    raise ValueError(
                        f"queries[{position}].target: derived targets require equivalence, properties, limit, or asymptotic"
                    )
                earlier = next(
                    (
                        source
                        for source in self.queries[:position]
                        if source.name == item.target.query
                    ),
                    None,
                )
                if earlier is None:
                    raise ValueError(
                        f"queries[{position}].target: derived query must reference an earlier query"
                    )
                if not isinstance(earlier, ClosedFormQuery):
                    raise ValueError(
                        f"queries[{position}].target: derived source must be a closed_form query"
                    )
        for item in self.queries:
            if isinstance(item, (LimitQuery, AsymptoticQuery)):
                infinity = str(item.point) in {"oo", "-oo"}
                if infinity == (item.direction is not None):
                    raise ValueError("finite points require direction and infinity forbids it")
        generated_results = 0
        for scenario in self.scenarios:
            population = 1
            for values in scenario.choices.values():
                population *= len(values)
            generated_results += population
        if generated_results > MAX_GENERATED_SCENARIO_RESULTS:
            raise ValueError("request generated scenario-result population exceeds its bound")
        return self


def _require_unique(values: Iterable[str], label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"{label} must be unique")


class OptimizationCandidate(StructuredModel):
    """Complete, replayable ordinary-analysis input owned by one plan."""

    syntax: FormulaSyntax
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    outputs: tuple[str, ...] = Field(min_length=1, max_length=MAX_EQUATIONS)

    @model_validator(mode="after")
    def complete_shape(self) -> "OptimizationCandidate":
        if (self.expression is None) != bool(self.equations):
            raise ValueError("candidate requires exactly one expression or nonempty equation list")
        if self.expression is not None:
            if self.outputs != ("expression",):
                raise ValueError("expression candidate output identity must be expression")
        else:
            equation_names = {item.name for item in self.equations}
            if len(set(self.outputs)) != len(self.outputs) or not set(self.outputs) <= equation_names:
                raise ValueError("candidate output identities must name unique transformed equations")
        return self


class OptimizeRequest(StructuredModel):
    """Explicit bounded optimization; analysis-only controls are intentionally absent."""

    syntax: FormulaSyntax
    operation: Literal["optimize"] = "optimize"
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    max_plans: int = Field(default=3, ge=1, le=16)

    @field_validator("max_plans")
    @classmethod
    def strict_max_plans(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("max_plans must be a strict integer")
        return value

    @model_validator(mode="after")
    def request_shape(self) -> "OptimizeRequest":
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        # Reuse the ordinary semantic contract, while refusing its analysis-only knobs.
        AnalysisRequest.model_validate({
            "syntax": self.syntax, "expression": self.expression, "equations": self.equations,
            "variables": self.variables, "functions": self.functions,
            "primitive_costs": self.primitive_costs, "assumptions": self.assumptions,
            "definitions": self.definitions,
        })
        return self


class CandidateComputation(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)

    @model_validator(mode="after")
    def one_computation(self) -> "CandidateComputation":
        if self.name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        _require_unique((item.name for item in self.equations), "equation names")
        return self

    def to_analysis_request(self) -> "AnalysisRequest":
        # Shared fields are supplied by CandidateComparisonRequest at call time.
        raise RuntimeError("comparison computation must be bound to shared request metadata")


class CandidateTargetReference(StructuredModel):
    candidate: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: Annotated[ExpressionTarget | EquationTarget, Field(discriminator="kind")]


class CandidateOutputMapping(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    targets: tuple[CandidateTargetReference, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def ordinary_name(self) -> "CandidateOutputMapping":
        if self.name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return self


class CandidateComparisonRequest(StructuredModel):
    operation: Literal["compare_candidates"] = "compare_candidates"
    syntax: FormulaSyntax
    candidates: tuple[CandidateComputation, ...] = Field(min_length=2, max_length=2)
    outputs: tuple[CandidateOutputMapping, ...] = Field(min_length=1, max_length=32)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)

    @model_validator(mode="after")
    def comparison_shape(self) -> "CandidateComparisonRequest":
        _require_unique((item.name for item in self.candidates), "candidate names")
        _require_unique((item.name for item in self.outputs), "output names")
        names = {item.name for item in self.candidates}
        for position, output in enumerate(self.outputs):
            mapped = tuple(item.candidate for item in output.targets)
            if set(mapped) != names or len(set(mapped)) != 2:
                raise ValueError(
                    f"outputs[{position}].targets must map each candidate exactly once"
                )
        # Reuse the ordinary request validator for shared-name restrictions,
        # callable collisions, variable bounds, and each computation shape.
        for candidate in self.candidates:
            self.analysis_request(candidate)
        return self

    def analysis_request(self, candidate: CandidateComputation) -> "AnalysisRequest":
        return AnalysisRequest(
            syntax=self.syntax,
            expression=candidate.expression,
            equations=candidate.equations,
            variables=self.variables,
            functions=self.functions,
            primitive_costs=self.primitive_costs,
            assumptions=self.assumptions,
            definitions=self.definitions,
        )


class CandidateAnalysisReport(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    analysis: "AnalysisSuccess"
    aggregate_work: BoundedQueryText | None = None

    @model_validator(mode="after")
    def direct_work_variant(self) -> "CandidateAnalysisReport":
        finite = self.analysis.direct_work_applicability == "finite"
        if finite != (self.aggregate_work is not None):
            raise ValueError(
                "finite candidate analysis requires aggregate work and non-finite analysis forbids it"
            )
        if not finite and not self.analysis.direct_work_blockers:
            raise ValueError("non-finite candidate analysis requires blockers")
        return self


class CandidateOutputComparison(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    targets: tuple[CandidateTargetReference, CandidateTargetReference]
    interface_status: Literal["compatible", "incompatible", "unresolved"]
    expanded_interpretations: "tuple[Interpretation, Interpretation] | None" = None
    answer: "QueryAnswer"

    @model_validator(mode="after")
    def qualified_output_shape(self) -> "CandidateOutputComparison":
        answer = self.answer
        if answer.check is not None or answer.derived_candidates or answer.constraint_uses:
            raise ValueError(
                "comparison outputs require one unchecked answer without candidates or constraint uses"
            )
        if self.interface_status == "incompatible":
            if (
                self.expanded_interpretations is not None
                or answer.conclusion != "inapplicable"
                or not answer.blockers
                or answer.evidence is not None
            ):
                raise ValueError("incompatible output has an invalid qualified shape")
            return self
        if self.interface_status == "unresolved":
            if (
                self.expanded_interpretations is not None
                or answer.conclusion != "unresolved"
                or not answer.blockers
                or answer.evidence is not None
            ):
                raise ValueError("unresolved interface has an invalid qualified shape")
            return self
        if self.expanded_interpretations is None:
            if (
                answer.conclusion != "unresolved"
                or not answer.blockers
                or answer.evidence is not None
            ):
                raise ValueError("unexpanded compatible output must be unresolved")
            return self
        if answer.conclusion in {"proved", "proved_under_assumptions"}:
            if not isinstance(answer.evidence, IdentityEvidence):
                raise ValueError("proved comparison output requires identity evidence")
        elif answer.conclusion == "disproved":
            if not isinstance(answer.evidence, CounterexampleEvidence):
                raise ValueError("disproved comparison output requires counterexample evidence")
        elif answer.conclusion == "unresolved":
            if not answer.blockers or answer.evidence is not None:
                raise ValueError("unresolved comparison output requires blockers only")
        else:
            raise ValueError("compatible expanded output has an invalid conclusion")
        return self


class CandidateWorkComparison(StructuredModel):
    metric: Literal["aggregate_abstract_work"] = "aggregate_abstract_work"
    candidate_names: tuple[str, str]
    candidate_works: tuple[BoundedQueryText | None, BoundedQueryText | None]
    delta: BoundedQueryText | None = None
    status: Literal[
        "not_comparable",
        "equal",
        "first_lower",
        "second_lower",
        "crossover",
        "unresolved",
    ]
    conditions: tuple[BoundedQueryText, ...] = Field(default=(), max_length=256)
    assumptions_used: "tuple[RelationshipUse, ...]" = Field(default=(), max_length=128)
    relevant_unsupported_assumptions: tuple[BoundedQueryText, ...] = Field(
        default=(), max_length=128
    )
    blockers: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)
    evidence: IdentityEvidence | PropertyEvidence | None = None

    @model_validator(mode="after")
    def qualified_work_shape(self) -> "CandidateWorkComparison":
        if len(set(self.candidate_names)) != 2 or any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in self.candidate_names
        ):
            raise ValueError("work candidate names must be unique ordinary identifiers")
        finite = all(work is not None for work in self.candidate_works)
        if not finite and self.delta is not None:
            raise ValueError("unavailable candidate work forbids a delta")
        if self.status == "not_comparable":
            if not self.blockers or self.evidence is not None:
                raise ValueError("not-comparable work requires blockers and no evidence")
            return self
        if self.status == "unresolved":
            if not self.blockers or self.evidence is not None:
                raise ValueError("unresolved work requires blockers and no evidence")
            if finite and self.delta is None:
                raise ValueError("unresolved finite work requires its symbolic delta")
            return self
        if not finite or self.delta is None:
            raise ValueError("comparable work requires two finite works and a delta")
        if self.blockers:
            raise ValueError("comparable work cannot carry blockers")
        if self.status == "equal":
            if not isinstance(self.evidence, IdentityEvidence):
                raise ValueError("equal work requires identity evidence")
        elif not isinstance(self.evidence, PropertyEvidence):
            raise ValueError("winner and crossover work require property evidence")
        return self


class CandidateComparisonSuccess(StructuredModel):
    kind: Literal["candidate_comparison"] = "candidate_comparison"
    status: Literal["success"] = "success"
    candidates: tuple[CandidateAnalysisReport, CandidateAnalysisReport]
    outputs: tuple[CandidateOutputComparison, ...] = Field(min_length=1, max_length=32)
    semantic_status: Literal[
        "proved_equal", "proved_equal_under_assumptions", "disproved", "unresolved"
    ]
    work_comparison: CandidateWorkComparison

    @model_validator(mode="after")
    def correlated_result(self) -> "CandidateComparisonSuccess":
        names = tuple(candidate.name for candidate in self.candidates)
        if len(set(names)) != 2:
            raise ValueError("candidate report names must be unique")
        _require_unique((output.name for output in self.outputs), "output names")
        for output in self.outputs:
            if tuple(target.candidate for target in output.targets) != names:
                raise ValueError("output targets must follow candidate report order")
        conclusions = {output.answer.conclusion for output in self.outputs}
        expected_semantic = (
            "disproved"
            if "disproved" in conclusions
            else "unresolved"
            if conclusions & {"unresolved", "inapplicable"}
            else "proved_equal_under_assumptions"
            if "proved_under_assumptions" in conclusions
            else "proved_equal"
        )
        if self.semantic_status != expected_semantic:
            raise ValueError("semantic status does not match mapped outputs")
        expected_works = tuple(candidate.aggregate_work for candidate in self.candidates)
        if (
            self.work_comparison.candidate_names != names
            or self.work_comparison.candidate_works != expected_works
        ):
            raise ValueError("work comparison does not match candidate report order")
        semantic_established = self.semantic_status in {
            "proved_equal",
            "proved_equal_under_assumptions",
        }
        if semantic_established == (self.work_comparison.status == "not_comparable"):
            raise ValueError("work comparability does not match semantic status")
        return self


type CandidateComparisonOutcome = Annotated[
    CandidateComparisonSuccess | AnalysisFailure, Field(discriminator="status")
]


class SourceLocation(StructuredModel):
    line: int = Field(ge=1)
    column: int = Field(ge=0)


class SourceSpan(StructuredModel):
    start: SourceLocation
    end: SourceLocation

    @model_validator(mode="after")
    def validate_order(self) -> "SourceSpan":
        if (self.end.line, self.end.column) < (self.start.line, self.start.column):
            raise ValueError("source span end must not precede start")
        return self


class SourceReference(StructuredModel):
    path: str = Field(min_length=1, max_length=160)
    span: SourceSpan | None = None
    excerpt: str | None = Field(default=None, max_length=160)


class AnalysisError(StructuredModel):
    code: AnalysisErrorCode
    message: str
    location: SourceLocation | None = None
    source: SourceReference | None = None
    supported_alternative: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_source_location(self) -> "AnalysisError":
        has_mismatched_location = (
            self.source is not None
            and self.source.span is not None
            and self.location != self.source.span.start
        )
        if has_mismatched_location:
            raise ValueError("error location must equal source span start")
        return self


class Interpretation(StructuredModel):
    normalized_sympy: str
    normalized_latex: str


class OperationCounts(StructuredModel):
    additions: int = Field(default=0, ge=0)
    subtractions: int = Field(default=0, ge=0)
    multiplications: int = Field(default=0, ge=0)
    divisions: int = Field(default=0, ge=0)
    powers: int = Field(default=0, ge=0)


class SymbolicOperationCounts(StructuredModel):
    additions: str = "0"
    subtractions: str = "0"
    multiplications: str = "0"
    divisions: str = "0"
    powers: str = "0"


type DirectWorkApplicability = Literal["finite", "not_finite"]


def _validate_direct_work_variant(
    applicability: DirectWorkApplicability,
    blockers: tuple[str, ...],
    nullable_values: tuple[object | None, ...],
) -> None:
    if applicability == "finite":
        if blockers or any(value is None for value in nullable_values):
            raise ValueError("finite direct work requires values and no blockers")
    elif not blockers or any(value is not None for value in nullable_values):
        raise ValueError("non-finite direct work requires null values and blockers")


class EffectiveIndexDomain(StructuredModel):
    index: str
    lower: str = Field(min_length=1, max_length=4096)
    upper: str = Field(min_length=1, max_length=4096)


class ConstraintUse(StructuredModel):
    equation: str
    name: str
    target: str
    relationship: str


class EquationEffectiveDomains(StructuredModel):
    equation: str
    domains: tuple[EffectiveIndexDomain, ...] = Field(max_length=MAX_DOMAINS_PER_EQUATION)


class EquationReport(StructuredModel):
    name: str
    interpretation: Interpretation
    operation_counts: OperationCounts
    aggregate_operation_counts: SymbolicOperationCounts | None
    aggregate_work: str | None
    direct_work_applicability: DirectWorkApplicability = "finite"
    direct_work_blockers: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    primitive_invocations: dict[str, str] | None = Field(default_factory=dict)
    unknown_costs: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    relationships_used: tuple["RelationshipUse", ...] = ()
    constraints: tuple[DomainConstraint, ...] = ()
    effective_domains: tuple[EffectiveIndexDomain, ...] = ()
    constraint_uses: tuple[ConstraintUse, ...] = ()

    @model_validator(mode="after")
    def validate_direct_work(self) -> "EquationReport":
        _validate_direct_work_variant(
            self.direct_work_applicability,
            self.direct_work_blockers,
            (
                self.aggregate_operation_counts,
                self.aggregate_work,
                self.primitive_invocations,
            ),
        )
        return self


class RelationshipUse(StructuredModel):
    name: str
    relationship: str


class IntervalResult(StructuredModel):
    lower: str
    upper: str
    lower_inclusive: bool
    upper_inclusive: bool
    lower_work: str
    upper_work: str
    infimum: str
    supremum: str
    infimum_attained: bool
    supremum_attained: bool
    conservative: bool = True


class ScenarioResult(StructuredModel):
    name: str
    substituted_work: str
    choice_work: dict[str, str] = Field(default_factory=dict)
    asymptotic: str | None = None
    interval: IntervalResult | None = None
    substitutions: dict[str, str] = Field(default_factory=dict)
    relationships_used: tuple[RelationshipUse, ...] = ()
    qualifications: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    effective_domains: tuple["EquationEffectiveDomains", ...] = ()
    choice_effective_domains: dict[str, tuple["EquationEffectiveDomains", ...]] = Field(
        default_factory=dict
    )


class ReuseReport(StructuredModel):
    producer: str
    consumer: str
    references: int = Field(ge=1)


class SystemReport(StructuredModel):
    equations: tuple[EquationReport, ...]
    aggregate_operation_counts: SymbolicOperationCounts | None
    total_work: str | None
    direct_work_applicability: DirectWorkApplicability = "finite"
    direct_work_blockers: tuple[str, ...] = ()
    dependency_edges: tuple[tuple[str, str], ...] = ()
    reuse: tuple[ReuseReport, ...] = ()
    primitive_invocations: dict[str, str] | None = Field(default_factory=dict)
    unknown_costs: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    extraction_opportunities: tuple[str, ...] = ()
    relationships_used: tuple[RelationshipUse, ...] = ()
    unused_assumptions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_direct_work(self) -> "SystemReport":
        _validate_direct_work_variant(
            self.direct_work_applicability,
            self.direct_work_blockers,
            (self.aggregate_operation_counts, self.total_work, self.primitive_invocations),
        )
        has_nonfinite_equation = any(
            equation.direct_work_applicability == "not_finite" for equation in self.equations
        )
        if has_nonfinite_equation != (self.direct_work_applicability == "not_finite"):
            raise ValueError("system direct work must agree with its equation reports")
        return self


class OptimizationTarget(StructuredModel):
    kind: Literal["expression", "equation"]
    name: str | None = None

    @model_validator(mode="after")
    def target_shape(self) -> "OptimizationTarget":
        if (self.kind == "equation") != (self.name is not None):
            raise ValueError("equation optimization targets require a name")
        return self


class OptimizationOccurrence(StructuredModel):
    path: tuple[int, ...] = Field(max_length=128)
    binders: tuple[str, ...] = Field(default=(), max_length=32)
    output_indices: tuple[str, ...] = Field(default=(), max_length=32)

    @field_validator("path")
    @classmethod
    def nonnegative_path(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(part < 0 for part in value):
            raise ValueError("optimization occurrence paths are nonnegative")
        return value


class OptimizationIntermediate(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: Interpretation
    scope_binders: tuple[str, ...] = Field(default=(), max_length=32)
    scope_output_indices: tuple[str, ...] = Field(default=(), max_length=32)


class OptimizationTransformation(StructuredModel):
    """One target-local edit in an atomic optimization suggestion."""

    target: OptimizationTarget
    occurrences: tuple[OptimizationOccurrence, ...] = Field(min_length=1, max_length=128)
    original: Interpretation
    proposed: Interpretation


class OptimizationSuggestion(StructuredModel):
    kind: Literal[
        "repeated_subexpression",
        "repeated_call",
        "reciprocal_reuse",
        "factoring",
        "redundant_operation_removal",
        "iterator_invariant_hoisting",
        "cross_equation_sharing",
        "horner",
    ]
    transformations: tuple[OptimizationTransformation, ...] = Field(min_length=1, max_length=128)
    intermediate: OptimizationIntermediate | None = None
    conclusion: Literal["proved", "proved_under_assumptions"]
    evidence: IdentityEvidence
    conditions: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)
    assumptions_used: tuple[RelationshipUse, ...] = Field(default=(), max_length=128)
    work_before: BoundedQueryText
    work_after: BoundedQueryText
    savings: BoundedQueryText
    finite_precision_qualification: Literal["exact_symbolic_only"] = "exact_symbolic_only"

    @model_validator(mode="after")
    def proved_positive_shape(self) -> "OptimizationSuggestion":
        targets = tuple(
            (item.target.kind, item.target.name) for item in self.transformations
        )
        if len(set(targets)) != len(targets):
            raise ValueError("optimization transformations require unique targets")
        if self.kind == "cross_equation_sharing":
            if len(self.transformations) < 2:
                raise ValueError("cross-equation sharing requires every affected target")
        elif len(self.transformations) != 1:
            raise ValueError("single-target optimization families require one transformation")
        numeric_work: list[Fraction | None] = []
        for value in (self.work_before, self.work_after, self.savings):
            try:
                numeric_work.append(Fraction(value))
            except (ValueError, ZeroDivisionError):
                numeric_work.append(None)
        before, after, savings = numeric_work
        if (
            (before is not None and before <= 0)
            or (after is not None and after < 0)
            or (savings is not None and savings <= 0)
        ):
            raise ValueError("optimization work before and savings must be positive; work after nonnegative")
        if (
            not self.savings
            or self.work_before == self.work_after
            or (
                before is not None
                and after is not None
                and savings is not None
                and (before <= after or before - after != savings)
            )
        ):
            raise ValueError("optimization suggestions require positive savings")
        requires_intermediate = self.kind in {
            "repeated_subexpression",
            "repeated_call",
            "reciprocal_reuse",
            "iterator_invariant_hoisting",
            "cross_equation_sharing",
        }
        if requires_intermediate != (self.intermediate is not None):
            raise ValueError("optimization family and intermediate shape are inconsistent")
        qualified = bool(self.conditions or self.assumptions_used)
        if (self.conclusion == "proved_under_assumptions") != qualified:
            raise ValueError("optimization proof conclusion must agree with its qualifications")
        return self


class OptimizationPlan(StructuredModel):
    """One independently replayable, verified optimization result."""

    identity: str = Field(min_length=1, max_length=262_144)
    candidate: OptimizationCandidate
    suggestion: OptimizationSuggestion


class OptimizationFailure(StructuredModel):
    status: Literal["failed"] = "failed"
    error: str = Field(min_length=1, max_length=4_096)


class OptimizationSuccess(StructuredModel):
    status: Literal["success"] = "success"
    requested_limit: int = Field(ge=1, le=16)
    search_status: Literal["complete", "incomplete"]
    plans: tuple[OptimizationPlan, ...] = Field(default=(), max_length=16)
    qualifications: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)


type OptimizeOutcome = Annotated[OptimizationSuccess | OptimizationFailure, Field(discriminator="status")]


class OptimizationReport(StructuredModel):
    requested_limit: int = Field(ge=0, le=16)
    status: Literal["disabled", "complete", "incomplete", "failed"]
    suggestions: tuple[OptimizationSuggestion, ...] = Field(default=(), max_length=16)
    plans: tuple[OptimizationPlan, ...] = Field(default=(), max_length=16)
    qualifications: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)

    @model_validator(mode="after")
    def report_shape(self) -> "OptimizationReport":
        if len(self.suggestions) > self.requested_limit or len(self.plans) > self.requested_limit:
            raise ValueError("optimization plans exceed requested limit")
        if self.plans and tuple(item.suggestion for item in self.plans) != self.suggestions:
            raise ValueError("optimization plans must project the same suggestions")
        if self.status == "disabled" and (
            self.requested_limit != 0 or self.suggestions or self.plans or self.qualifications
        ):
            raise ValueError("disabled optimization requires an empty zero-limit report")
        if self.requested_limit == 0 and self.status != "disabled":
            raise ValueError("zero-limit optimization must be disabled")
        if self.status == "incomplete" and not self.qualifications:
            raise ValueError("incomplete optimization requires an exhaustion qualification")
        if self.status == "complete" and self.qualifications:
            raise ValueError("complete optimization cannot carry search qualifications")
        if self.status == "failed" and (self.suggestions or self.plans or not self.qualifications):
            raise ValueError("failed optimization must contain only a bounded diagnostic")
        return self


class AnalysisSuccess(StructuredModel):
    status: Literal["success"] = "success"
    interpretation: Interpretation
    operation_counts: OperationCounts
    abstract_work: int | None = Field(default=None, ge=0)
    direct_work_applicability: DirectWorkApplicability = "finite"
    direct_work_blockers: tuple[str, ...] = ()
    system: SystemReport | None = None
    scenarios: tuple[ScenarioResult, ...] = ()
    queries: tuple[QueryResult, ...] = ()
    optimization: OptimizationReport = Field(
        default_factory=lambda: OptimizationReport(requested_limit=0, status="disabled")
    )

    @model_validator(mode="after")
    def validate_direct_work(self) -> "AnalysisSuccess":
        _validate_direct_work_variant(
            self.direct_work_applicability,
            self.direct_work_blockers,
            (self.abstract_work,),
        )
        if (
            self.system is not None
            and self.system.direct_work_applicability != self.direct_work_applicability
        ):
            raise ValueError("analysis direct work must agree with its system report")
        return self


class AnalysisFailure(StructuredModel):
    status: Literal["failure"] = "failure"
    error: AnalysisError


type AnalysisOutcome = Annotated[AnalysisSuccess | AnalysisFailure, Field(discriminator="status")]


# Dominance is intentionally a separate request family: it shares computation
# metadata with ordinary analysis but cannot carry scenarios or queries.
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
        if self.range is not None and self.range.lower == self.range.upper and not (
            self.range.lower_inclusive and self.range.upper_inclusive
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
            if domain in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL} and signed <= 0:
                raise ValueError(f"fixed.{name} must be positive for its declared domain")
            if domain in {
                MathematicalDomain.NONNEGATIVE_INTEGER,
                MathematicalDomain.NONNEGATIVE_REAL,
            } and signed < 0:
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
            if lower is None or lower < previous_upper or (
                lower == previous_upper and lower_inclusive and previous_inclusive
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
            or (
                inner_lower == outer_lower
                and (outer_lower_inclusive or not inner_lower_inclusive)
            )
        )
    )
    upper_ok = outer_upper is None or (
        inner_upper is not None
        and (
            inner_upper < outer_upper
            or (
                inner_upper == outer_upper
                and (outer_upper_inclusive or not inner_upper_inclusive)
            )
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
    effective_lower, effective_upper, lower_inclusive, upper_inclusive = _range_bounds(
        effective
    )
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
            if gap_start <= gap_end and {
                Fraction(item) for item in range(gap_start, gap_end + 1)
            } - excluded:
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
        if (
            not previous_inclusive
            and not current_inclusive
            and previous_upper not in excluded
        ):
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
            effective_lower, effective_upper, effective_lower_inclusive, effective_upper_inclusive = _range_bounds(self.effective_range)
            domain_lower = Fraction(0) if self.axis_domain in {
                MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL,
                MathematicalDomain.NONNEGATIVE_INTEGER, MathematicalDomain.NONNEGATIVE_REAL,
            } else None
            domain_lower_inclusive = self.axis_domain in {
                MathematicalDomain.NONNEGATIVE_INTEGER, MathematicalDomain.NONNEGATIVE_REAL
            }
            if domain_lower is not None and (
                effective_lower is None or effective_lower < domain_lower or (
                    effective_lower == domain_lower and effective_lower_inclusive and not domain_lower_inclusive
                )
            ):
                raise ValueError("effective range must lie within the axis domain")
            if self.requested_range is not None:
                requested_lower, requested_upper, requested_lower_inclusive, requested_upper_inclusive = _range_bounds(self.requested_range)
                if (requested_lower is not None and (
                    effective_lower is None or effective_lower < requested_lower or (
                        effective_lower == requested_lower and effective_lower_inclusive and not requested_lower_inclusive
                    )
                )) or (requested_upper is not None and (
                    effective_upper is None or effective_upper > requested_upper or (
                        effective_upper == requested_upper and effective_upper_inclusive and not requested_upper_inclusive
                    )
                )):
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
        if self.dominance_status == "complete" and self.terms and tuple(
            item for item in ids if item not in active
        ) != self.never_dominant:
            raise ValueError("never-dominant ids must be the proved complement")
        expected_pairs = tuple(combinations(ids, 2))
        pairs = tuple(item.pair for item in self.evidence)
        if len(pairs) != len(set(pairs)) or any(pair not in expected_pairs for pair in pairs):
            raise ValueError("dominance evidence pairs must be unique reported term pairs")
        if self.dominance_status == "complete" and self.terms and pairs != expected_pairs:
            raise ValueError("complete dominance requires every pair in canonical order")
        exclusion_values = tuple(item.value for item in self.exclusions)
        if exclusion_values != tuple(
            sorted(set(exclusion_values), key=_dominance_exact_sort_key)
        ):
            raise ValueError("dominance exclusions must be unique and ordered")
        if self.axis_domain.is_integer and any(
            _dominance_exact_sort_key(item).denominator != 1
            for item in exclusion_values
        ):
            raise ValueError("integer dominance exclusions must be integral")
        _validate_dominance_cell_order(self.cells, exclusion_values)
        if self.effective_range is not None:
            effective_bounds = _range_bounds(self.effective_range)
            if any(
                not _dominance_bounds_within(
                    _dominance_cell_bounds(cell), effective_bounds
                )
                for cell in self.cells
            ) or any(
                not _dominance_bounds_within(
                    (point, point, True, True), effective_bounds
                )
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
