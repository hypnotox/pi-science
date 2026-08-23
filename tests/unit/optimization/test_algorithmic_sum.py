# pyright: reportPrivateUsage=false

import pytest


def test_exact_algorithmic_sum_v1_opt_in_is_strict_and_candidate_local() -> None:
    from py_science.formula import OptimizationConfig
    from pydantic import ValidationError

    assert OptimizationConfig().enabled_algorithmic_families == ()
    assert OptimizationConfig.model_validate_json(
        '{"enabled_algorithmic_families":[]}'
    ).enabled_algorithmic_families == ()
    assert OptimizationConfig(
        enabled_algorithmic_families=("finite_polynomial_sum_v1",)
    ).enabled_algorithmic_families == ("finite_polynomial_sum_v1",)
    with pytest.raises(ValidationError):
        OptimizationConfig(
            enabled_algorithmic_families=(
                "finite_polynomial_sum_v1",
                "finite_polynomial_sum_v1",
            )
        )
    with pytest.raises(ValidationError):
        OptimizationConfig.model_validate(
            {"enabled_algorithmic_families": ["future_family"]}
        )


def test_exact_algorithmic_sum_v1_absent_empty_query_parity_and_enabled_plan() -> None:
    from py_science.formula import (
        AnalysisRequest,
        ClosedFormQuery,
        FormulaSyntax,
        OptimizationConfig,
        analyze,
    )

    source = "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))"
    query = (ClosedFormQuery(name="closed"),)
    absent = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=source, queries=query)
    )
    empty = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=source,
            queries=query,
            optimization=OptimizationConfig(enabled_algorithmic_families=()),
        )
    )
    enabled = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=source,
            queries=query,
            optimization=OptimizationConfig(
                max_suggestions=16,
                enabled_algorithmic_families=("finite_polynomial_sum_v1",),
            ),
        )
    )

    assert absent.status == "success"
    assert empty.status == "success"
    assert enabled.status == "success"
    assert absent.queries == empty.queries == enabled.queries
    assert absent.optimization == empty.optimization
    plan = next(
        plan
        for plan in enabled.optimization.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    assert plan.suggestion.tier == plan.trace[-1].tier
    assert any(step.tier == "exact_algorithmic_v1" for step in plan.trace)
    assert plan.candidate.expression is not None and "Sum(" not in plan.candidate.expression
    assert int(plan.suggestion.objective_savings) > 0


def test_exact_algorithmic_sum_v1_mixes_with_algebraic_search_deterministically() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    def plans(source: str, limit: int = 16):
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=source,
                variables={
                    name: VariableDeclaration(domain=MathematicalDomain.REAL)
                    for name in ("x", "y", "z")
                },
                optimization=OptimizationConfig(
                    max_suggestions=limit,
                    enabled_algorithmic_families=("finite_polynomial_sum_v1",),
                ),
            )
        )
        assert outcome.status == "success"
        return outcome.optimization.plans

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
    assert [plan.identity for plan in alpha_renamed] == [
        plan.identity for plan in population
    ]
    assert [tuple(step.kind for step in plan.trace) for plan in alpha_renamed] == [
        tuple(step.kind for step in plan.trace) for plan in population
    ]


def test_exact_algorithmic_sum_v1_direct_request_keeps_opt_in_out_of_replay() -> None:
    from py_science.formula import FormulaSyntax, OptimizeRequest, optimize

    outcome = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))",
            max_plans=16,
            enabled_algorithmic_families=("finite_polynomial_sum_v1",),
        )
    )
    assert outcome.status == "success"
    plan = next(
        plan
        for plan in outcome.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    assert "enabled_algorithmic_families" not in plan.identity
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
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=source,
            optimization=OptimizationConfig(
                max_suggestions=16,
                enabled_algorithmic_families=("finite_polynomial_sum_v1",),
            ),
        )
    )

    assert outcome.status == "success"
    assert all(
        not any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
        for plan in outcome.optimization.plans
    )
    assert not any(
        "algorithmic" in qualification or "polynomial" in qualification
        for qualification in outcome.optimization.qualifications
    )


def test_exact_algorithmic_sum_v1_uses_existing_proof_budget() -> None:
    from dataclasses import replace

    from py_science.formula import (
        AnalysisFailure,
        AnalysisRequest,
        FormulaSyntax,
        OptimizationConfig,
    )
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import _optimization_report, _OptimizationBudgetConfig

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))",
        optimization=OptimizationConfig(
            max_suggestions=16,
            enabled_algorithmic_families=("finite_polynomial_sum_v1",),
        ),
    )
    computed = analyze_retained(request)
    assert not isinstance(computed, AnalysisFailure)

    report = _optimization_report(
        request,
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), proofs=0),
        analyzer=analyze_retained,
    )

    assert report.status == "incomplete"
    assert report.plans == ()
    assert report.qualifications == (
        "optimization depth-one proof steps budget exhausted (measured 1, configured 0)",
    )


def test_exact_algorithmic_sum_v1_system_multiplicity_and_weighted_prefix() -> None:
    from py_science.formula import (
        AnalysisRequest,
        OptimizationSuccess,
        OptimizeRequest,
        analyze,
        optimize,
    )

    source = "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))"
    system = analyze(
        AnalysisRequest.model_validate_json(
            """{
              "syntax": "sympy",
              "equations": [{
                "name": "value",
                "expression": "Eq(value[k], 3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100)))",
                "domains": {"k": {"lower": "0", "upper": "3"}}
              }],
              "optimization": {
                "max_suggestions": 16,
                "enabled_algorithmic_families": ["finite_polynomial_sum_v1"]
              }
            }"""
        )
    )
    assert system.status == "success"
    system_plan = next(
        plan
        for plan in system.optimization.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    assert system_plan.suggestion.objective_before == "82416"
    assert system_plan.suggestion.objective_after == "0"
    assert system_plan.suggestion.objective_savings == "82416"
    assert system_plan.trace[0].transformations[0].occurrences[0].output_indices == ("k",)

    def weighted(limit: int):
        return optimize(
            OptimizeRequest.model_validate_json(
                f"""{{
                  "syntax": "sympy",
                  "operation": "optimize",
                  "expression": "{source}",
                  "max_plans": {limit},
                  "enabled_algorithmic_families": ["finite_polynomial_sum_v1"],
                  "objective": {{
                    "kind": "weighted_operations_v1",
                    "weights": {{
                      "additions": "2", "subtractions": "2",
                      "multiplications": "2", "divisions": "2", "powers": "2"
                    }}
                  }}
                }}"""
            )
        )

    one, many = weighted(1), weighted(16)
    assert isinstance(one, OptimizationSuccess)
    assert isinstance(many, OptimizationSuccess)
    assert one.plans == many.plans[:1]
    suggestion = one.plans[0].suggestion
    assert (suggestion.objective_before, suggestion.objective_after) == ("41208", "0")
    assert suggestion.objective_savings == "41208"
