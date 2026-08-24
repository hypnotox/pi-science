# ruff: noqa: E501
# pyright: reportPrivateUsage=false, reportUnusedFunction=false
from fractions import Fraction
from typing import Annotated, Literal

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
    Interpretation,
    PrimitiveCost,
    RelationshipUse,
    VariableDeclaration,
    _exact_scenario_scalar,
    _validate_output_identities,
)
from py_science.formula.contracts.evidence import BoundedQueryText, IdentityEvidence
from py_science.formula.exact_values import parse_exact_scalar
from pydantic import Field, field_validator, model_validator


class UnitWorkObjective(StructuredModel):
    kind: Literal["unit_work_v1"] = "unit_work_v1"


class WeightedOperationWeights(StructuredModel):
    additions: ExactScenarioScalar
    subtractions: ExactScenarioScalar
    multiplications: ExactScenarioScalar
    divisions: ExactScenarioScalar
    powers: ExactScenarioScalar

    @field_validator(
        "additions", "subtractions", "multiplications", "divisions", "powers", mode="before"
    )
    @classmethod
    def canonical_positive_scalar(cls, value: object) -> str:
        rendered = _exact_scenario_scalar(value)
        parsed = parse_exact_scalar(rendered)
        assert parsed is not None
        if parsed.numerator <= 0:
            raise ValueError("objective weights must be strictly positive")
        return rendered


class WeightedOperationsObjective(StructuredModel):
    kind: Literal["weighted_operations_v1"] = "weighted_operations_v1"
    weights: WeightedOperationWeights


type OptimizationObjective = Annotated[
    UnitWorkObjective | WeightedOperationsObjective, Field(discriminator="kind")
]


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
        _validate_output_identities(self.expression, self.equations, self.outputs, required=True)
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


type OptimizationKind = Literal[
    "repeated_subexpression",
    "repeated_call",
    "reciprocal_reuse",
    "factoring",
    "redundant_operation_removal",
    "iterator_invariant_hoisting",
    "cross_equation_sharing",
    "horner",
    "finite_polynomial_sum_v1",
]


type OptimizationTier = Literal["exact_algebraic_v1", "exact_algorithmic_v1"]


OPTIMIZATION_FAMILY_TIERS: dict[OptimizationKind, OptimizationTier] = {
    "repeated_subexpression": "exact_algebraic_v1",
    "repeated_call": "exact_algebraic_v1",
    "reciprocal_reuse": "exact_algebraic_v1",
    "factoring": "exact_algebraic_v1",
    "redundant_operation_removal": "exact_algebraic_v1",
    "iterator_invariant_hoisting": "exact_algebraic_v1",
    "cross_equation_sharing": "exact_algebraic_v1",
    "horner": "exact_algebraic_v1",
    "finite_polynomial_sum_v1": "exact_algorithmic_v1",
}


class OptimizationSuggestion(StructuredModel):
    kind: OptimizationKind
    tier: OptimizationTier
    transformations: tuple[OptimizationTransformation, ...] = Field(min_length=1, max_length=128)
    intermediate: OptimizationIntermediate | None = None
    conclusion: Literal["proved", "proved_under_assumptions"]
    evidence: IdentityEvidence
    conditions: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)
    assumptions_used: tuple[RelationshipUse, ...] = Field(default=(), max_length=128)
    objective_before: BoundedQueryText
    objective_after: BoundedQueryText
    objective_savings: BoundedQueryText
    ordering: "OptimizationOrdering"
    finite_precision_qualification: Literal["exact_symbolic_only"] = "exact_symbolic_only"

    @model_validator(mode="after")
    def proved_positive_shape(self) -> "OptimizationSuggestion":
        if self.tier != OPTIMIZATION_FAMILY_TIERS[self.kind]:
            raise ValueError("optimization family and tier are inconsistent")
        targets = tuple((item.target.kind, item.target.name) for item in self.transformations)
        if len(set(targets)) != len(targets):
            raise ValueError("optimization transformations require unique targets")
        if self.kind == "cross_equation_sharing":
            if len(self.transformations) < 2:
                raise ValueError("cross-equation sharing requires every affected target")
        elif len(self.transformations) != 1:
            raise ValueError("single-target optimization families require one transformation")
        numeric_work: list[Fraction | None] = []
        for value in (self.objective_before, self.objective_after, self.objective_savings):
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
            raise ValueError(
                "optimization objective before and savings must be positive; objective after nonnegative"
            )
        if (
            not self.objective_savings
            or self.objective_before == self.objective_after
            or (
                before is not None
                and after is not None
                and savings is not None
                and (before <= after or before - after != savings)
            )
        ):
            raise ValueError("optimization suggestions require positive objective savings")
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

    # Python attribute aliases preserve source compatibility; they are not serialized.
    @property
    def work_before(self) -> str:
        return self.objective_before

    @property
    def work_after(self) -> str:
        return self.objective_after

    @property
    def savings(self) -> str:
        return self.objective_savings


class OptimizationOrdering(StructuredModel):
    position: int = Field(ge=1, le=16)
    relation_to_previous: (
        Literal["previous_proved_superior", "deterministic_non_superiority"] | None
    )

    @model_validator(mode="after")
    def ordering_shape(self) -> "OptimizationOrdering":
        if (self.position == 1) != (self.relation_to_previous is None):
            raise ValueError("only the first optimization position has no previous relation")
        return self


class OptimizationTraceStep(StructuredModel):
    """One complete, parent-relative transition in a replayable plan."""

    kind: OptimizationKind
    tier: OptimizationTier
    transformations: tuple[OptimizationTransformation, ...] = Field(min_length=1, max_length=128)
    intermediate: OptimizationIntermediate | None = None
    conclusion: Literal["proved", "proved_under_assumptions"]
    evidence: IdentityEvidence
    conditions: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)
    assumptions_used: tuple[RelationshipUse, ...] = Field(default=(), max_length=128)
    objective_before: BoundedQueryText
    objective_after: BoundedQueryText
    objective_savings: BoundedQueryText
    candidate: OptimizationCandidate
    identity: str = Field(min_length=1, max_length=262_144)
    finite_precision_qualification: Literal["exact_symbolic_only"] = "exact_symbolic_only"

    @model_validator(mode="after")
    def trace_step_shape(self) -> "OptimizationTraceStep":
        if self.tier != OPTIMIZATION_FAMILY_TIERS[self.kind]:
            raise ValueError("optimization trace family and tier are inconsistent")
        if self.identity != self.candidate.model_dump_json(exclude_none=True):
            raise ValueError("optimization trace identity must match its candidate")
        if len({(item.target.kind, item.target.name) for item in self.transformations}) != len(
            self.transformations
        ):
            raise ValueError("optimization trace transformations require unique targets")
        return self


class StrictImprovementClaim(StructuredModel):
    """The exact claim independently established for one published plan."""

    kind: Literal["strict_improvement"] = "strict_improvement"
    proof_policy: Literal["verifier_backed_v1"] = "verifier_backed_v1"
    objective: OptimizationObjective
    semantics: Literal["exact_symbolic_v1"] = "exact_symbolic_v1"
    work_semantics: Literal["aggregate_abstract_work_v1"] = "aggregate_abstract_work_v1"
    search_policy: Literal["bounded_goal_v1"] = "bounded_goal_v1"
    families: tuple[OptimizationKind, ...] = Field(min_length=1, max_length=16)
    monotonic_depth: Literal[2] = 2
    engine: Literal["goal_optimizer_v1"] = "goal_optimizer_v1"


class OptimizationPlan(StructuredModel):
    """One independently replayable, verified optimization result."""

    identity: str = Field(min_length=1, max_length=262_144)
    objective: OptimizationObjective
    claim: StrictImprovementClaim
    candidate: OptimizationCandidate
    suggestion: OptimizationSuggestion
    trace: tuple[OptimizationTraceStep, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def trace_final_shape(self) -> "OptimizationPlan":
        if self.trace[-1].candidate != self.candidate or self.trace[-1].identity != self.identity:
            raise ValueError("optimization plan must equal its final trace step")
        if self.suggestion.tier != self.trace[-1].tier:
            raise ValueError("optimization summary tier must match the final trace step")
        if self.claim.objective != self.objective:
            raise ValueError("optimization plan objective must match its strict-improvement claim")
        return self
