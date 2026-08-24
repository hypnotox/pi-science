# pyright: reportPrivateUsage=false

import pytest


def test_deterministic_ranking_prefers_unconditional_then_larger_exact_savings() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        VariableDeclaration,
    )

    unconditional = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="reciprocal", expression="Eq(a, 1/x + 1/x)"),
                EquationRequest(name="polynomial", expression="Eq(b, (y + 1) * (y + 1))"),
            ),
            variables={
                name: VariableDeclaration(domain=MathematicalDomain.REAL) for name in ("x", "y")
            },
        )
    )
    ranked = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1) * (x + 1) + (x + 1) + (y + 1) * (y + 1)",
        )
    )
    assert unconditional.status == "success"
    unconditional_suggestions = tuple(plan.suggestion for plan in unconditional.plans)
    assert unconditional_suggestions[0].conclusion == "proved"
    assert ranked.status == "success"
    ranked_suggestions = tuple(plan.suggestion for plan in ranked.plans)
    exact_savings = [
        int(item.savings)
        for item in ranked_suggestions
        if item.conclusion == "proved" and item.savings.isdigit()
    ]
    assert exact_savings == sorted(exact_savings, reverse=True)


def test_comparable_symbolic_savings_rank_by_proof_before_stable_ties() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        VariableDeclaration,
    )

    equations = tuple(
        EquationRequest(
            name=name,
            expression=f"Eq({name}[{index}], x[{index}]*x[{index}] {operator} 1)",
            domains={index: IndexDomain(lower="0", upper=upper)},
        )
        for name, index, upper, operator in (
            ("a", "i", "N", "+"),
            ("b", "j", "N", "-"),
            ("c", "k", "2*N", "+"),
            ("d", "l", "2*N", "-"),
        )
    )
    outcome = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=equations,
            variables={
                "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
        )
    )
    assert outcome.status == "success"
    sharing = [
        plan.trace[0]
        for plan in outcome.plans
        if len(plan.trace) == 1 and plan.trace[0].kind == "cross_equation_sharing"
    ]
    assert [(item.transformations[0].target.name, item.objective_savings) for item in sharing] == [
        ("c", "2*N + 1"),
        ("a", "N + 1"),
    ]


def _weighted_objective(*, powers: str = "1", operation_weight: str = "1"):
    from py_science.formula import WeightedOperationsObjective

    return WeightedOperationsObjective.model_validate(
        {
            "kind": "weighted_operations_v1",
            "weights": {
                "additions": operation_weight,
                "subtractions": operation_weight,
                "multiplications": operation_weight,
                "divisions": operation_weight,
                "powers": powers,
            },
        }
    )


def test_objective_v1_default_and_weighted_request_shapes() -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    ordinary = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1")
    direct = goal_request(ordinary, objective=_weighted_objective(powers="5/2"))
    assert direct.goal.objective.kind == "weighted_operations_v1"
    assert direct.goal.objective.weights.powers == "5/2"
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate({**ordinary.model_dump(), "optimization": {}})
    with pytest.raises(ValidationError):
        type(direct).model_validate({**direct.model_dump(), "objective": {"kind": "unit_work_v1"}})


@pytest.mark.parametrize("weight", ["0", "-1", True, "wat", "1/0"])
def test_objective_v1_rejects_nonpositive_or_malformed_weights(weight: object) -> None:
    with pytest.raises(ValueError):
        _weighted_objective(operation_weight=weight)  # type: ignore[arg-type]


def test_objective_v1_rejects_incomplete_extra_and_over_bound_weights() -> None:
    from py_science.formula import WeightedOperationsObjective
    from pydantic import ValidationError

    weights: dict[str, object] = {
        "additions": "1",
        "subtractions": "1",
        "multiplications": "1",
        "divisions": "1",
        "powers": "1",
    }
    assert _weighted_objective().kind == "weighted_operations_v1"
    for invalid in (
        {**weights, "additions": "1e4097"},
        {key: value for key, value in weights.items() if key != "powers"},
        {**weights, "opaque": "1"},
    ):
        with pytest.raises(ValidationError):
            WeightedOperationsObjective.model_validate(
                {"kind": "weighted_operations_v1", "weights": invalid}
            )


def test_objective_v1_default_all_one_parity_and_stable_identity() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y*z + y*w)"
    )
    default = optimize_analysis(request)
    all_one = optimize_analysis(request, objective=_weighted_objective())
    assert default.status == "success" and all_one.status == "success"
    assert [plan.identity for plan in default.plans] == [plan.identity for plan in all_one.plans]
    assert [plan.candidate for plan in default.plans] == [plan.candidate for plan in all_one.plans]
    assert [item.objective_savings for item in (plan.suggestion for plan in default.plans)] == [
        item.objective_savings for item in (plan.suggestion for plan in all_one.plans)
    ]


def test_objective_v1_weighted_power_reverses_plan_order() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y*z + y*w)"
    )
    default = optimize_analysis(request)
    weighted = optimize_analysis(request, objective=_weighted_objective(powers="5/2"))
    assert default.status == "success" and weighted.status == "success"
    assert default.plans[0].objective.kind == "unit_work_v1"
    assert weighted.plans[0].objective.kind == "weighted_operations_v1"
    assert weighted.plans[1].suggestion.ordering.relation_to_previous in {
        "previous_proved_superior",
        "deterministic_non_superiority",
    }


def test_objective_v1_opaque_work_keeps_fixed_coefficient_one() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax, PrimitiveCost

    outcome = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f(x) + f(x)",
            primitive_costs=(PrimitiveCost(name="f", parameters=("z",), work="5"),),
        ),
        objective=_weighted_objective(operation_weight="2"),
    )
    assert outcome.status == "success"
    suggestion = outcome.plans[0].suggestion
    assert suggestion.kind == "repeated_call"
    assert (
        suggestion.objective_before,
        suggestion.objective_after,
        suggestion.objective_savings,
    ) == ("12", "7", "5")


def test_objective_v1_plans_carry_canonical_provenance_and_evidence() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    outcome = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y*z + y*w)"),
        objective=_weighted_objective(powers="5/2"),
    )
    assert outcome.status == "success"
    plan = outcome.plans[0]
    assert plan.objective.model_dump() == _weighted_objective(powers="5/2").model_dump()
    assert plan.suggestion.objective_before
    assert plan.suggestion.ordering.position == 1
    assert plan.suggestion.ordering.relation_to_previous is None


def test_objective_v1_qualified_mismatches_never_claim_adjacent_superiority() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        RelationshipUse,
    )
    from py_science.formula.expressions import IntegerLiteral
    from py_science.formula.optimization import (
        _Accepted,
        _adjacent_ordering_relation,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1)*(x + 1) + (y*z + y*w)",
    )
    outcome = optimize_analysis(request)
    assert outcome.status == "success" and len(outcome.plans) >= 2
    previous, current = outcome.plans[:2]
    mismatches = (
        current.suggestion.model_copy(update={"conclusion": "proved_under_assumptions"}),
        current.suggestion.model_copy(update={"conditions": ("x != 0",)}),
        current.suggestion.model_copy(
            update={"assumptions_used": (RelationshipUse(name="positive", relationship="x > 0"),)}
        ),
    )
    for qualified in mismatches:
        assert (
            _adjacent_ordering_relation(
                _Accepted(previous.suggestion, request, IntegerLiteral(2)),
                _Accepted(qualified, request, IntegerLiteral(1)),
                None,  # type: ignore[arg-type]
                _OptimizationBudget(),
            )
            == "deterministic_non_superiority"
        )


def test_objective_v1_comparison_qualifications_never_claim_superiority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from py_science.formula._optimization import objectives as objectives_owner
    from py_science.formula.expressions import Symbol
    from py_science.formula.optimization import (
        _Accepted,
        _adjacent_ordering_relation,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1)*(x + 1) + (y*z + y*w)",
    )
    outcome = optimize_analysis(request)
    assert outcome.status == "success" and len(outcome.plans) >= 2
    previous, current = outcome.plans[:2]

    def qualified_relation(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status="second_lower", conditions=("N > M",), assumptions_used=())

    monkeypatch.setattr(objectives_owner, "compare_aggregate_work", qualified_relation)
    assert (
        _adjacent_ordering_relation(
            _Accepted(
                previous.suggestion.model_copy(update={"objective_savings": "N"}),
                request,
                Symbol("N"),
            ),
            _Accepted(
                current.suggestion.model_copy(update={"objective_savings": "M"}),
                request,
                Symbol("M"),
            ),
            None,  # type: ignore[arg-type]
            _OptimizationBudget(),
        )
        == "deterministic_non_superiority"
    )


def test_objective_v1_result_models_reject_population_drift() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationResult
    from pydantic import ValidationError

    outcome = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y*z + y*w)")
    )
    assert outcome.status == "success" and len(outcome.plans) >= 2
    plans = outcome.plans[:2]
    drifted_second = plans[1].model_copy(
        update={
            "suggestion": plans[1].suggestion.model_copy(
                update={"ordering": plans[1].suggestion.ordering.model_copy(update={"position": 3})}
            )
        }
    )
    with pytest.raises(ValidationError):
        OptimizationResult.model_validate(
            {**outcome.model_dump(), "plans": (plans[0], drifted_second)}
        )

    objective_drift = plans[1].model_copy(update={"objective": _weighted_objective()})
    with pytest.raises(ValidationError):
        OptimizationResult.model_validate(
            {**outcome.model_dump(), "plans": (plans[0], objective_drift)}
        )
