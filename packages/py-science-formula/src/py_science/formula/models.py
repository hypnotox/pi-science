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
        if {"Eq", "Sum"} & (definition_names | cost_names):
            raise ValueError("Eq and Sum are reserved mathematical constructs")
        return self


def _require_unique(values: Iterable[str], label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"{label} must be unique")


class SourceLocation(StructuredModel):
    line: int = Field(ge=1)
    column: int = Field(ge=0)


class AnalysisError(StructuredModel):
    code: AnalysisErrorCode
    message: str
    location: SourceLocation | None = None


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


class EquationReport(StructuredModel):
    name: str
    interpretation: Interpretation
    operation_counts: OperationCounts
    aggregate_operation_counts: SymbolicOperationCounts
    aggregate_work: str
    dependencies: tuple[str, ...] = ()
    primitive_invocations: dict[str, str] = Field(default_factory=dict)
    unknown_costs: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()


class ReuseReport(StructuredModel):
    producer: str
    consumer: str
    references: int = Field(ge=1)


class SystemReport(StructuredModel):
    equations: tuple[EquationReport, ...]
    aggregate_operation_counts: SymbolicOperationCounts
    total_work: str
    dependency_edges: tuple[tuple[str, str], ...] = ()
    reuse: tuple[ReuseReport, ...] = ()
    primitive_invocations: dict[str, str] = Field(default_factory=dict)
    unknown_costs: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    extraction_opportunities: tuple[str, ...] = ()


class AnalysisSuccess(StructuredModel):
    status: Literal["success"] = "success"
    interpretation: Interpretation
    operation_counts: OperationCounts
    abstract_work: int = Field(ge=0)
    system: SystemReport | None = None


class AnalysisFailure(StructuredModel):
    status: Literal["failure"] = "failure"
    error: AnalysisError


type AnalysisOutcome = Annotated[AnalysisSuccess | AnalysisFailure, Field(discriminator="status")]
