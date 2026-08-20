"""Neutral retained computation data shared by analysis consumers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from py_science.formula.domains import OutputDomain
from py_science.formula.expressions import Equation, Expression, Relationship
from py_science.formula.models import (
    AnalysisSuccess,
    DomainConstraint,
)
from py_science.formula.work import SymbolicTally, WorkAnalysis


@dataclass(frozen=True, slots=True)
class ParsedEquation:
    name: str
    submitted_constraints: tuple[DomainConstraint, ...]
    formula: Equation
    domains: Mapping[str, tuple[Expression, Expression]]
    constraints: tuple[tuple[str, str, Relationship], ...]
    output_domains: tuple[OutputDomain, ...]
    domain_order: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Producer:
    equation_name: str
    value_name: str
    arity: int


@dataclass(frozen=True, slots=True)
class NamedRelationship:
    name: str
    source: str
    value: Relationship


@dataclass(frozen=True, slots=True)
class NamedDefinition:
    name: str
    source: str
    expression: Expression
    domain_qualification: str | None = None


@dataclass(frozen=True, slots=True)
class Knowledge:
    assumptions: tuple[NamedRelationship, ...] = ()
    definitions: tuple[NamedDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class RetainedWorkAnalysis:
    """Immutable snapshot of original submitted-graph work."""

    operations: SymbolicTally
    opaque_work: Expression
    invocations: Mapping[str, Expression]
    unknown_costs: frozenset[str]
    unresolved: frozenset[str]
    direct_work_blockers: frozenset[str]

    @property
    def total_work(self) -> Expression:
        return WorkAnalysis(operations=self.operations, opaque_work=self.opaque_work).total_work


@dataclass(frozen=True, slots=True)
class RetainedComputation:
    """Validated analysis state for comparison and future optimization consumers."""

    success: AnalysisSuccess
    expression: Expression | None
    equations: tuple[ParsedEquation, ...]
    producers: Mapping[str, Producer]
    dependency_order: tuple[str, ...]
    equation_analyses: Mapping[str, RetainedWorkAnalysis]
    aggregate_analysis: RetainedWorkAnalysis
    knowledge: Knowledge
