# pyright: reportPrivateUsage=false

import pytest


def test_exact_algorithmic_sum_v1_is_fixed_policy_and_former_controls_are_rejected() -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizeRequest
    from pydantic import ValidationError

    request = goal_request(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"), projection_limit=1
    )
    assert request.search.kind == "bounded_goal_v1"
    former_controls: tuple[dict[str, object], ...] = (
        {"enabled_algorithmic_families": []},
        {"enabled_algorithmic_families": ["finite_polynomial_sum_v1"]},
        {"max_plans": 1},
    )
    for former in former_controls:
        with pytest.raises(ValidationError):
            OptimizeRequest.model_validate({**request.model_dump(), **former})


def test_exact_algorithmic_sum_v1_query_analysis_is_separate_and_plan_is_enabled() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, ClosedFormQuery, FormulaSyntax, analyze

    source = "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))"
    ordinary = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=source,
            queries=(ClosedFormQuery(name="closed"),),
        )
    )
    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=source), projection_limit=16
    )

    assert ordinary.status == "success" and ordinary.queries
    assert result.status == "success"
    plan = next(
        plan
        for plan in result.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    assert plan.suggestion.tier == plan.trace[-1].tier
    assert any(step.tier == "exact_algorithmic_v1" for step in plan.trace)
    assert plan.candidate.expression is not None and "Sum(" not in plan.candidate.expression
    assert int(plan.suggestion.objective_savings) > 0


def test_exact_algorithmic_sum_v1_mixes_with_algebraic_search_deterministically() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        MathematicalDomain,
        VariableDeclaration,
    )

    def plans(source: str, limit: int = 16):
        outcome = optimize_analysis(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=source,
                variables={
                    name: VariableDeclaration(domain=MathematicalDomain.REAL)
                    for name in ("x", "y", "z")
                },
            ),
            projection_limit=limit,
        )
        assert outcome.status == "success"
        return outcome.plans

    source = "x*y + x*z + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))"
    population = plans(source)
    mixed = next(plan for plan in population if len(plan.trace) == 2)
    assert tuple((step.kind, step.tier) for step in mixed.trace) == (
        ("finite_polynomial_sum_v1", "exact_algorithmic_v1"),
        ("factoring", "exact_algebraic_v1"),
    )
    assert mixed.candidate.expression == "x*(y + z) + 21591275"
    assert mixed.suggestion.objective_savings == "20604"
    assert plans(source, 1) == population[:1]
    alpha_renamed = plans(
        "x*y + x*z + Sum(Sum(a*b + b**2, (b, 0, a)), (a, 0, 100))"
    )
    assert [plan.identity for plan in alpha_renamed] == [plan.identity for plan in population]
    assert [tuple(step.kind for step in plan.trace) for plan in alpha_renamed] == [
        tuple(step.kind for step in plan.trace) for plan in population
    ]


def test_exact_algorithmic_sum_v1_request_keeps_search_policy_out_of_replay() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    outcome = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))",
        ),
        projection_limit=16,
    )
    assert outcome.status == "success"
    plan = next(
        plan
        for plan in outcome.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    assert "bounded_goal_v1" not in plan.identity
    assert plan.trace[0].transformations[0].occurrences[0].path == ()


@pytest.mark.parametrize(
    "source",
    (
        "Sum(Sum(k**9, (l, 0, 1)), (k, 0, 100))",
        "Sum(Sum(k, (l, 0, 1)), (k, 0, oo))",
        "Sum(Sum(k, (l, 0, 1)), (k, n, 100))",
        "Sum(Sum(k, (l, 0, 1)), (k, 0, 100)) + "
        "Sum(Sum(k, (l, 0, 1)), (k, 0, 100))",
        "Sum(Sum(f(k), (l, 0, 1)), (k, 0, 100))",
    ),
)
def test_exact_algorithmic_sum_v1_refusals_are_silent(source: str) -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    outcome = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=source), projection_limit=16
    )
    assert outcome.status == "success"
    assert all(
        not any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
        for plan in outcome.plans
    )
    assert not any(
        "algorithmic" in qualification or "polynomial" in qualification
        for qualification in outcome.search_scope.qualifications
    )


def test_exact_algorithmic_sum_v1_uses_existing_proof_budget() -> None:
    from dataclasses import replace

    from goal_requests import goal_request
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization.search import _optimization_result
    from py_science.formula.optimization import _OptimizationBudgetConfig

    computation = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))",
    )
    request = goal_request(computation, projection_limit=16)
    computed = analyze_retained(computation)
    assert not isinstance(computed, AnalysisFailure)

    result = _optimization_result(
        request,
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), proofs=0),
        analyzer=analyze_retained,
    )

    assert result.search_scope.completion == "incomplete"
    assert result.plans == ()
    assert result.search_scope.qualifications == (
        "optimization depth-one proof steps budget exhausted (measured 1, configured 0)",
    )


def test_exact_algorithmic_sum_v1_system_multiplicity_and_weighted_prefix() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationResult,
        WeightedOperationsObjective,
        WeightedOperationWeights,
    )

    source = "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))"
    computation = AnalysisRequest.model_validate_json(
        """{
          "syntax": "sympy",
          "equations": [{
            "name": "value",
            "expression": "Eq(value[k], 3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100)))",
            "domains": {"k": {"lower": "0", "upper": "3"}}
          }]
        }"""
    )
    system = optimize_analysis(computation, projection_limit=16)
    assert isinstance(system, OptimizationResult)
    system_plan = next(
        plan
        for plan in system.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    assert system_plan.suggestion.objective_before == "82416"
    assert system_plan.suggestion.objective_after == "0"
    assert system_plan.suggestion.objective_savings == "82416"
    assert system_plan.trace[0].transformations[0].occurrences[0].output_indices == ("k",)

    objective = WeightedOperationsObjective(
        weights=WeightedOperationWeights(
            additions="2", subtractions="2", multiplications="2", divisions="2", powers="2"
        )
    )

    def weighted(limit: int):
        return optimize_analysis(
            AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=source),
            projection_limit=limit,
            objective=objective,
        )

    one, many = weighted(1), weighted(16)
    assert isinstance(one, OptimizationResult)
    assert isinstance(many, OptimizationResult)
    assert one.plans == many.plans[:1]
    suggestion = one.plans[0].suggestion
    assert (suggestion.objective_before, suggestion.objective_after) == ("41208", "0")
    assert suggestion.objective_savings == "41208"
