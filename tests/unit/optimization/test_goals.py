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
        operation="optimize",
        expression="x + 0",
        goal=GoalSpec(
            kind="preserve_all_outputs_v1",
            semantics="exact_symbolic_v1",
            operating_domain="submitted_domain_v1",
            objective=UnitWorkObjective(),
        ),
        search=BoundedGoalSearchPolicy(kind="bounded_goal_v1"),
        proof=VerifierBackedProofPolicy(kind="verifier_backed_v1"),
        projection_limit=1,
    )
    assert request.goal.kind == "preserve_all_outputs_v1"
    assert request.goal.operating_domain == "submitted_domain_v1"
    assert request.search.kind == "bounded_goal_v1"
    assert request.proof.kind == "verifier_backed_v1"
    payload = request.model_dump()
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate({**payload, "objective": {"kind": "unit_work_v1"}})
    for omitted in ("operation", "goal", "search", "proof"):
        with pytest.raises(ValidationError):
            OptimizeRequest.model_validate(
                {key: value for key, value in payload.items() if key != omitted}
            )
    for omitted in ("kind", "semantics", "operating_domain"):
        goal = {key: value for key, value in payload["goal"].items() if key != omitted}
        with pytest.raises(ValidationError):
            OptimizeRequest.model_validate({**payload, "goal": goal})
    for field in ("search", "proof"):
        with pytest.raises(ValidationError):
            OptimizeRequest.model_validate({**payload, field: {}})


def test_ordinary_analysis_has_no_optimization_field() -> None:
    from py_science.formula.models import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            {"syntax": FormulaSyntax.SYMPY, "expression": "x", "optimization": {}}
        )
