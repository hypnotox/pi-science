"""Explicit declarative optimization-goal, search, and result contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ._base import StructuredModel
from .evidence import BoundedQueryText
from .optimization import (
    OptimizationKind,
    OptimizationObjective,
    OptimizationPlan,
    SearchLimits,
    StrictImprovementClaim,
)


class GoalSpec(StructuredModel):
    """The fixed initial goal: preserve submitted outputs and minimize abstract work."""

    kind: Literal["preserve_all_outputs_v1"]
    semantics: Literal["exact_symbolic_v1"]
    operating_domain: Literal["submitted_domain_v1"]
    objective: OptimizationObjective


class BoundedGoalSearchPolicy(StructuredModel):
    kind: Literal["bounded_goal_v1"]


class VerifierBackedProofPolicy(StructuredModel):
    kind: Literal["verifier_backed_v1"]


class SearchScope(StructuredModel):
    policy: Literal["bounded_goal_v1"] = "bounded_goal_v1"
    families: tuple[OptimizationKind, ...] = Field(min_length=1, max_length=16)
    monotonic_depth: Literal[2] = 2
    engine: Literal["goal_optimizer_v1"] = "goal_optimizer_v1"
    limits: SearchLimits
    completion: Literal["complete", "incomplete"]
    qualifications: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)

    @model_validator(mode="after")
    def completion_matches_qualifications(self) -> SearchScope:
        if len(set(self.families)) != len(self.families):
            raise ValueError("search families must be unique")
        if (self.completion == "incomplete") != bool(self.qualifications):
            raise ValueError("search completion must agree with qualifications")
        return self


class OptimizationBlocker(StructuredModel):
    reason: Literal["missing_primitive_cost", "unproved_domain_or_cardinality", "evaluator_limit"]
    required_information: Literal[
        "declare_primitive_cost", "declare_domain_or_cardinality", "reduce_evaluator_complexity"
    ]
    family: OptimizationKind
    target: str = Field(min_length=1, max_length=160)


class DeterministicRankedPrefixSelection(StructuredModel):
    kind: Literal["deterministic_ranked_prefix"] = "deterministic_ranked_prefix"
    projection_limit: int = Field(ge=1, le=16)


class OptimizationResult(StructuredModel):
    """A bounded explicit-operation result with independent search and projection state."""

    status: Literal["success"] = "success"
    projection_limit: int = Field(ge=1, le=16)
    classification: Literal["plans_returned", "no_applicable_candidate", "no_verified_improvement"]
    selection: DeterministicRankedPrefixSelection
    search_scope: SearchScope
    projection_status: Literal["complete", "truncated"] = "complete"
    projection_qualifications: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)
    blockers: tuple[OptimizationBlocker, ...] = Field(default=(), max_length=16)
    plans: tuple[OptimizationPlan, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def result_shape(self) -> OptimizationResult:
        if self.selection.projection_limit != self.projection_limit:
            raise ValueError("selection must use the result projection limit")
        if len(self.plans) > self.projection_limit:
            raise ValueError("optimization plans exceed projection limit")
        if (self.projection_status == "truncated") != bool(self.projection_qualifications):
            raise ValueError("projection status must agree with qualifications")
        if self.classification == "plans_returned":
            if not self.plans and self.projection_status != "truncated":
                raise ValueError("plans_returned requires a retained plan or truncated projection")
        elif self.plans:
            raise ValueError("empty classifications cannot include plans")
        for position, plan in enumerate(self.plans, start=1):
            if plan.suggestion.ordering.position != position:
                raise ValueError("optimization plan positions must be contiguous")
            if plan.claim.families != self.search_scope.families:
                raise ValueError("plan claim families must match the reported search scope")
            if plan.claim.monotonic_depth != self.search_scope.monotonic_depth:
                raise ValueError("plan claim depth must match the reported search scope")
            if plan.claim.engine != self.search_scope.engine:
                raise ValueError("plan claim engine must match the reported search scope")
            if plan.claim.limits != self.search_scope.limits:
                raise ValueError("plan claim limits must match the reported search scope")
        return self


class OptimizationFailure(StructuredModel):
    status: Literal["failure"] = "failure"
    error: str = Field(min_length=1, max_length=4_096)


type OptimizeOutcome = Annotated[
    OptimizationResult | OptimizationFailure, Field(discriminator="status")
]


__all__ = [
    "BoundedGoalSearchPolicy",
    "DeterministicRankedPrefixSelection",
    "GoalSpec",
    "OptimizationBlocker",
    "OptimizationFailure",
    "OptimizationResult",
    "OptimizeOutcome",
    "SearchLimits",
    "SearchScope",
    "StrictImprovementClaim",
    "VerifierBackedProofPolicy",
]
