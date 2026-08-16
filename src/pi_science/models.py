from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StructuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FormulaSyntax(StrEnum):
    SYMPY = "sympy"


class EvaluationErrorCode(StrEnum):
    MALFORMED_SYNTAX = "malformed_syntax"
    UNSUPPORTED_CONSTRUCT = "unsupported_construct"
    EXPRESSION_TOO_COMPLEX = "expression_too_complex"
    NORMALIZATION_FAILED = "normalization_failed"


class EvaluationRequest(StructuredModel):
    syntax: FormulaSyntax
    expression: str


class SourceLocation(StructuredModel):
    line: int = Field(ge=1)
    column: int = Field(ge=0)


class EvaluationError(StructuredModel):
    code: EvaluationErrorCode
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


class EvaluationSuccess(StructuredModel):
    status: Literal["success"] = "success"
    interpretation: Interpretation
    operation_counts: OperationCounts
    abstract_work: int = Field(ge=0)


class EvaluationFailure(StructuredModel):
    status: Literal["failure"] = "failure"
    error: EvaluationError


type EvaluationOutcome = Annotated[
    EvaluationSuccess | EvaluationFailure,
    Field(discriminator="status"),
]
