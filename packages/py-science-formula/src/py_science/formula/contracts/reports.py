from enum import StrEnum
from typing import Annotated, Literal

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.contracts.common import (
    ConstraintUse,
    DirectWorkApplicability,
    DomainConstraint,
    EffectiveIndexDomain,
    EquationEffectiveDomains,
    Interpretation,
    IntervalResult,
    OperationCounts,
    RelationshipUse,
    SymbolicOperationCounts,
)
from py_science.formula.contracts.queries import QueryResult
from pydantic import Field, model_validator


class AnalysisErrorCode(StrEnum):
    MALFORMED_SYNTAX = "malformed_syntax"
    UNSUPPORTED_CONSTRUCT = "unsupported_construct"
    EXPRESSION_TOO_COMPLEX = "expression_too_complex"
    NORMALIZATION_FAILED = "normalization_failed"
    INVALID_SYSTEM = "invalid_system"


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
