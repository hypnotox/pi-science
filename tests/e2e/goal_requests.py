"""Test helpers for the public explicit goal-driven optimization contract."""

from __future__ import annotations

from py_science.formula import (
    AnalysisRequest,
    BoundedGoalSearchPolicy,
    GoalSpec,
    OptimizationObjective,
    OptimizationResult,
    OptimizeRequest,
    UnitWorkObjective,
    VerifierBackedProofPolicy,
    optimize,
)


def goal_request(
    request: AnalysisRequest,
    *,
    projection_limit: int = 16,
    objective: OptimizationObjective | None = None,
) -> OptimizeRequest:
    """Project an ordinary computation request into the explicit public operation."""
    computation = request.model_dump(exclude={"outputs", "scenarios", "queries"})
    return OptimizeRequest.model_validate(
        {
            **computation,
            "goal": GoalSpec(objective=objective or UnitWorkObjective()).model_dump(),
            "search": BoundedGoalSearchPolicy().model_dump(),
            "proof": VerifierBackedProofPolicy().model_dump(),
            "projection_limit": projection_limit,
        }
    )


def optimize_analysis(
    request: AnalysisRequest,
    *,
    projection_limit: int = 16,
    objective: OptimizationObjective | None = None,
) -> OptimizationResult:
    """Run a fixture that is expected to produce a successful optimization result."""
    outcome = optimize(
        goal_request(request, projection_limit=projection_limit, objective=objective)
    )
    assert isinstance(outcome, OptimizationResult)
    return outcome
