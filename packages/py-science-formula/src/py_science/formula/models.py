from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StructuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FormulaSyntax(StrEnum):
    SYMPY = "sympy"


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
    domain: str


class EquationRequest(StructuredModel):
    name: str = Field(min_length=1, max_length=128)
    expression: str
    domains: dict[str, IndexDomain] = Field(default_factory=dict)


class FunctionDefinition(StructuredModel):
    name: str
    parameters: tuple[str, ...]
    body: str


class PrimitiveCost(StructuredModel):
    name: str
    parameters: tuple[str, ...]
    work: str


class AnalysisRequest(StructuredModel):
    syntax: FormulaSyntax
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = ()
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = ()
    primitive_costs: tuple[PrimitiveCost, ...] = ()

    @model_validator(mode="after")
    def one_input(self) -> "AnalysisRequest":
        if (self.expression is None) != (bool(self.equations)):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        if (
            len(self.equations) > 128
            or len(self.functions) > 128
            or len(self.variables) > 256
            or len(self.primitive_costs) > 128
        ):
            raise ValueError("request collection exceeds its bound")
        if len({e.name for e in self.equations}) != len(self.equations):
            raise ValueError("equation names must be unique")
        if len({f.name for f in self.functions}) != len(self.functions):
            raise ValueError("function names must be unique")
        if len({p.name for p in self.primitive_costs}) != len(self.primitive_costs):
            raise ValueError("primitive cost names must be unique")
        return self


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


class EquationReport(StructuredModel):
    name: str
    interpretation: Interpretation
    operation_counts: OperationCounts
    aggregate_work: str
    dependencies: tuple[str, ...] = ()


class SystemReport(StructuredModel):
    equations: tuple[EquationReport, ...]
    total_work: str
    dependency_edges: tuple[tuple[str, str], ...] = ()
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
