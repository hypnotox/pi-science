import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
MAX_DOMAINS_PER_EQUATION = 32
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


class IntervalBound(StructuredModel):
    lower: int
    upper: int

    @model_validator(mode="after")
    def validate_order(self) -> "IntervalBound":
        if self.lower > self.upper:
            raise ValueError("interval lower bound must not exceed its upper bound")
        if max(self.lower.bit_length(), self.upper.bit_length()) > MAX_SCENARIO_INTEGER_BITS:
            raise ValueError("interval integer exceeds its size bound")
        return self


class Scenario(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    fixed: dict[str, int] = Field(default_factory=dict)
    choices: dict[str, tuple[int, ...]] = Field(default_factory=dict)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    asymptotic: tuple[str, ...] = ()
    bounds: dict[str, IntervalBound] = Field(default_factory=dict)

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
            len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
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
        integers = [
            *self.fixed.values(),
            *(value for values in self.choices.values() for value in values),
        ]
        if any(value.bit_length() > MAX_SCENARIO_INTEGER_BITS for value in integers):
            raise ValueError("scenario integer exceeds its size bound")
        generated = 1
        for values in self.choices.values():
            generated *= len(values)
            if generated > MAX_GENERATED_SCENARIO_RESULTS:
                raise ValueError("scenario generated-result population exceeds its bound")
        return self


class EquationRequest(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str
    domains: dict[str, IndexDomain] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_domains(self) -> "EquationRequest":
        if len(self.domains) > MAX_DOMAINS_PER_EQUATION:
            raise ValueError("equation domain collection exceeds its bound")
        if any(
            len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
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
        _validate_parameters(self.parameters)
        return self


class PrimitiveCost(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    parameters: tuple[str, ...] = Field(max_length=MAX_PARAMETERS)
    work: str

    @model_validator(mode="after")
    def validate_parameters(self) -> "PrimitiveCost":
        _validate_parameters(self.parameters)
        return self


def _validate_parameters(parameters: tuple[str, ...]) -> None:
    if len(set(parameters)) != len(parameters):
        raise ValueError("function parameters must be unique")
    if any(
        len(parameter) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, parameter) is None
        for parameter in parameters
    ):
        raise ValueError("function parameters must be ordinary identifiers")


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

    @model_validator(mode="after")
    def validate_request(self) -> "AnalysisRequest":
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        if len(self.variables) > MAX_VARIABLES:
            raise ValueError("variable collection exceeds its bound")
        if any(
            len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
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
        if {"Eq", "Sum", "Max", "cardinality"} & callable_names or any(
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
    lower_work: str
    upper_work: str
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
            equation.direct_work_applicability == "not_finite"
            for equation in self.equations
        )
        if has_nonfinite_equation != (self.direct_work_applicability == "not_finite"):
            raise ValueError("system direct work must agree with its equation reports")
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
