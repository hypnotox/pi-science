"""Neutral retained-computation facts shared below service and optimizer policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from py_science.formula.domains import OutputDomain
from py_science.formula.expressions import Equation, Expression, Relationship
from py_science.formula.models import (
    AnalysisRequest,
    AnalysisSuccess,
    DomainConstraint,
    RelationshipUse,
    Scenario,
)
from py_science.formula.work import SymbolicTally, WorkAnalysis, WorkContext


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


def retain_work_analysis(analysis: WorkAnalysis) -> RetainedWorkAnalysis:
    """Freeze one submitted-graph work result for retained consumers."""
    return RetainedWorkAnalysis(
        operations=analysis.operations,
        opaque_work=analysis.opaque_work,
        invocations=MappingProxyType(dict(analysis.invocations)),
        unknown_costs=frozenset(analysis.unknown_costs),
        unresolved=frozenset(analysis.unresolved),
        direct_work_blockers=frozenset(analysis.direct_work_blockers),
    )


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

    def as_work_analysis(self) -> WorkAnalysis:
        """Reconstruct mutable work only at a consuming specialization boundary."""
        return WorkAnalysis(
            operations=self.operations,
            opaque_work=self.opaque_work,
            invocations=dict(self.invocations),
            unknown_costs=set(self.unknown_costs),
            unresolved=set(self.unresolved),
            direct_work_blockers=set(self.direct_work_blockers),
        )


@dataclass(frozen=True, slots=True)
class PreparedScenario:
    """Immutable neutral state handed once to service scenario enrichment."""

    scenario: Scenario
    definitions: Mapping[str, tuple[str, Expression]]
    definition_qualifications: Mapping[str, str | None]


@dataclass(frozen=True, slots=True)
class PreparedScenarioState:
    """Scenario inputs prepared during neutral validation without service policy."""

    request: AnalysisRequest
    scenarios: tuple[PreparedScenario, ...]
    general_analysis: RetainedWorkAnalysis
    general_relationships: tuple[RelationshipUse, ...]
    knowledge: Knowledge
    equations: tuple[ParsedEquation, ...]


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
    work_context: WorkContext
    scenario_state: PreparedScenarioState | None = None


def retained_computation(
    *,
    success: AnalysisSuccess,
    expression: Expression | None,
    equations: tuple[ParsedEquation, ...],
    producers: Mapping[str, Producer],
    dependency_order: tuple[str, ...],
    equation_analyses: Mapping[str, RetainedWorkAnalysis],
    aggregate_analysis: RetainedWorkAnalysis,
    knowledge: Knowledge,
    work_context: WorkContext,
    scenario_state: PreparedScenarioState | None = None,
) -> RetainedComputation:
    """Construct the one immutable retained-analysis handoff."""
    return RetainedComputation(
        success=success,
        expression=expression,
        equations=equations,
        producers=producers,
        dependency_order=dependency_order,
        equation_analyses=equation_analyses,
        aggregate_analysis=aggregate_analysis,
        knowledge=knowledge,
        work_context=work_context,
        scenario_state=scenario_state,
    )
