import pytest
from pydantic import ValidationError


def test_explicit_goal_request_requires_fixed_goal_search_proof_and_projection() -> None:
    from py_science.formula.contracts.goals import (
        BoundedGoalSearchPolicy,
        GoalSpec,
        VerifierBackedProofPolicy,
    )
    from py_science.formula.contracts.optimization import UnitWorkObjective
    from py_science.formula.models import FormulaSyntax, OptimizeRequest

    request = OptimizeRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x + 0",
        goal=GoalSpec(objective=UnitWorkObjective()),
        search=BoundedGoalSearchPolicy(),
        proof=VerifierBackedProofPolicy(),
        projection_limit=1,
    )
    assert request.goal.kind == "preserve_all_outputs_v1"
    assert request.search.kind == "bounded_goal_v1"
    assert request.proof.kind == "verifier_backed_v1"
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(
            {**request.model_dump(), "objective": {"kind": "unit_work_v1"}}
        )


def test_ordinary_analysis_has_no_optimization_field() -> None:
    from py_science.formula.models import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            {"syntax": FormulaSyntax.SYMPY, "expression": "x", "optimization": {}}
        )
