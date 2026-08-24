# pyright: reportPrivateUsage=false
from dataclasses import replace
from typing import cast

import pytest
from goal_requests import goal_request, optimize_analysis
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str) -> Expression:
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_advice_has_a_separate_result_allowance_and_excludes_its_key_from_base() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service

    assert formula_service.MAX_RESULT_BYTES == 262_144
    assert formula_service.MAX_OPTIMIZATION_BYTES == 262_144
    ordinary = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    assert ordinary.status == "success"
    assert "optimization" not in ordinary.model_dump()
    result = optimize_analysis(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    assert result.status == "success"
    assert len(result.model_dump_json().encode("utf-8")) < 65_536


def test_candidate_budget_exhaustion_preserves_already_proved_advice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from py_science.formula._optimization import budgets as budget_owner

    monkeypatch.setattr(budget_owner, "MAX_OPTIMIZATION_CANDIDATES", 1)
    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)")
    )
    assert result.search_scope.completion == "incomplete"
    assert result.search_scope.qualifications == (
        "optimization depth-one generated transitions budget exhausted (measured 2, configured 1)",
    )
    assert len(result.plans) == 1


def test_historical_exact_base_result_limit_still_succeeds() -> None:
    from py_science.formula import AnalysisSuccess
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation, OperationCounts, ScenarioResult

    def outcome_with_padding(length: int) -> AnalysisSuccess:
        return AnalysisSuccess(
            interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
            operation_counts=OperationCounts(),
            abstract_work=0,
            scenarios=(
                ScenarioResult(
                    name="padding", substituted_work="0", qualifications=("x" * length,)
                ),
            ),
        )

    overhead = len(outcome_with_padding(0).model_dump_json().encode("utf-8"))
    exact = outcome_with_padding(formula_service.MAX_RESULT_BYTES - overhead)
    assert len(exact.model_dump_json().encode("utf-8")) == formula_service.MAX_RESULT_BYTES
    assert formula_service._bound_result(exact).status == "success"  # pyright: ignore[reportPrivateUsage]
    assert (
        formula_service._bound_result(
            outcome_with_padding(formula_service.MAX_RESULT_BYTES - overhead + 1)
        ).status
        == "failure"
    )  # pyright: ignore[reportPrivateUsage]


def _oversized_result(text: str, *, multibyte: bool = False):
    from py_science.formula import AnalysisRequest, FormulaSyntax

    result = optimize_analysis(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))
    assert result.plans
    plan = result.plans[0]
    proposed = plan.suggestion.transformations[0].proposed.model_copy(
        update={"normalized_sympy": text, "normalized_latex": text}
    )
    suggestion = plan.suggestion.model_copy(
        update={
            "transformations": (
                plan.suggestion.transformations[0].model_copy(update={"proposed": proposed}),
            )
        }
    )
    return result.model_copy(
        update={"plans": (plan.model_copy(update={"suggestion": suggestion}),)}
    )


def test_oversized_advice_truncates_without_replacing_base_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import service
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 30_000)
    bounded = service._bound_optimization_result(_oversized_result("x" * 140_000))
    assert bounded.status == "success"
    assert bounded.plans == ()
    assert bounded.projection_status == "truncated"
    assert bounded.projection_qualifications[0].startswith(
        "optimization result bytes budget exhausted (measured "
    )
    assert "configured 30000" in bounded.projection_qualifications[0]


def test_exact_base_and_maximum_field_contribution_preserve_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import service
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 5_000)
    result = _oversized_result("y" * 10_000)
    bounded = service._bound_optimization_result(result)
    assert bounded.status == "success"
    assert bounded.projection_status == "truncated"
    assert bounded.projection_qualifications == (
        "optimization result bytes budget exhausted (measured "
        f"{len(result.model_dump_json().encode('utf-8'))}, configured 5000)",
    )
    assert len(bounded.model_dump_json().encode("utf-8")) <= 5_000


def test_independent_budget_qualifications_report_measured_and_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from py_science.formula._optimization import budgets as budget_owner

    monkeypatch.setattr(budget_owner, "MAX_OPTIMIZATION_CANDIDATES", 1)
    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)")
    )
    qualification = result.search_scope.qualifications[0]
    assert (
        "generated transitions" in qualification
        and "measured 2" in qualification
        and "configured 1" in qualification
    )
    assert result.plans


def test_cross_equation_domain_signature_overflow_is_a_typed_incomplete_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        VariableDeclaration,
    )
    from py_science.formula._optimization.families import cross_equation_sharing
    from py_science.formula.expressions import ExpressionTooComplex

    def exhausted(*_args: object, **_kwargs: object) -> object:
        raise ExpressionTooComplex("bounded substitution exhausted")

    monkeypatch.setattr(cross_equation_sharing, "substitute", exhausted)
    result = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="left",
                    expression="Eq(left[i], x[i] + 1)",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
                EquationRequest(
                    name="right",
                    expression="Eq(right[j], x[j] - 1)",
                    domains={"j": IndexDomain(lower="0", upper="N")},
                ),
            ),
            variables={
                "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
        )
    )
    assert result.search_scope.completion == "incomplete"
    assert any(
        "per-candidate transformation nodes budget exhausted" in item
        for item in result.search_scope.qualifications
    )


def test_recursive_horner_inspection_is_charged_before_backend_descent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from py_science.formula._optimization import budgets as budget_owner
    from py_science.formula.expressions import expression_node_count

    expression = "2*x**3 + 3*x**2 + 4*x + 5"
    nodes = expression_node_count(_expression(expression))
    monkeypatch.setattr(budget_owner, "MAX_OPTIMIZATION_INSPECTIONS", nodes)
    result = optimize_analysis(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
    assert result.search_scope.completion == "incomplete"
    assert f"measured {nodes * 2}, configured {nodes}" in result.search_scope.qualifications[0]


@pytest.mark.parametrize(
    ("constant", "configured", "resource"),
    [
        ("MAX_OPTIMIZATION_INSPECTIONS", 1, "inspected nodes"),
        ("MAX_OPTIMIZATION_TRANSFORM_NODES", 1, "transformation nodes"),
        ("MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES", 1, "aggregate transformation nodes"),
        ("MAX_OPTIMIZATION_PROOFS", 0, "proof steps"),
        ("MAX_OPTIMIZATION_PROOF_NODES", 1, "proof nodes"),
        ("MAX_OPTIMIZATION_WORK_NODES", 1, "work-comparison nodes"),
    ],
)
def test_each_independent_search_budget_preserves_base_success(
    monkeypatch: pytest.MonkeyPatch, constant: str, configured: int, resource: str
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from py_science.formula._optimization import budgets as budget_owner

    monkeypatch.setattr(budget_owner, constant, configured)
    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)")
    )
    assert result.search_scope.completion == "incomplete"
    assert any(resource in item for item in result.search_scope.qualifications)
    assert all(
        "measured" in item and "configured" in item for item in result.search_scope.qualifications
    )


def test_multibyte_advice_limit_measures_encoded_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    from py_science.formula import service
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 30_000)
    bounded = service._bound_optimization_result(_oversized_result("é" * 140_000))
    assert bounded.projection_status == "truncated"
    assert (
        "measured" in bounded.projection_qualifications[0]
        and "configured 30000" in bounded.projection_qualifications[0]
    )


def test_optimize_result_bound_keeps_every_plan_that_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, service
    from py_science.formula._service import result_bounds

    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(alpha + beta)*(alpha + beta) + 0"),
        projection_limit=16,
    )
    assert len(result.plans) >= 2
    oversized = result.model_copy(
        update={
            "search_scope": result.search_scope.model_copy(
                update={"completion": "incomplete", "qualifications": ("x" * 10_000,)}
            )
        }
    )
    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 30_000)
    bounded = service._bound_optimization_result(oversized)
    assert (
        bounded.search_scope.completion == "incomplete" and bounded.projection_status == "complete"
    )
    assert len(bounded.plans) == len(result.plans)


def test_optimize_result_bound_keeps_largest_fitting_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, service
    from py_science.formula._service import result_bounds

    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(alpha + beta)*(alpha + beta) + 0"),
        projection_limit=16,
    )
    oversized = result.model_copy(
        update={
            "search_scope": result.search_scope.model_copy(
                update={"completion": "incomplete", "qualifications": ("x" * 10_000,)}
            )
        }
    )
    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 12_000)
    bounded = service._bound_optimization_result(oversized)
    assert bounded.projection_status == "truncated" and len(bounded.plans) < len(result.plans)
    assert len(bounded.model_dump_json().encode("utf-8")) <= result_bounds.MAX_OPTIMIZATION_BYTES


def test_optimize_result_bound_handles_oversized_empty_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationResult, service
    from py_science.formula._service import result_bounds

    seed = optimize_analysis(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    oversized = OptimizationResult(
        projection_limit=seed.projection_limit,
        classification="no_applicable_candidate",
        selection=seed.selection,
        search_scope=seed.search_scope.model_copy(
            update={"completion": "incomplete", "qualifications": ("x" * 3_700,)}
        ),
    )
    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 5_000)
    assert len(oversized.model_dump_json().encode("utf-8")) <= result_bounds.MAX_OPTIMIZATION_BYTES
    bounded = service._bound_optimization_result(oversized)
    assert bounded == oversized
    assert bounded.plans == () and bounded.search_scope.completion == "incomplete"


def test_optimize_operation_bounds_duplicated_plan_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 6_000)
    result = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(alpha + beta)*(alpha + beta) + 0"),
        projection_limit=16,
    )
    assert result.search_scope.completion == "complete" and result.projection_status == "truncated"
    assert (
        result.projection_qualifications and len(result.model_dump_json().encode("utf-8")) <= 6_000
    )


def test_composed_search_v1_budget_seams_distinguish_transition_and_final_proofs() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import (
        _generate_candidate_lanes,
        _optimization_result,
        _OptimizationBudget,
        _OptimizationBudgetConfig,
        _RetainedLaneCollector,
    )

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0")
    computed = analyze_retained(request)
    assert not isinstance(computed, AnalysisFailure)
    budget = _OptimizationBudget(replace(_OptimizationBudgetConfig(), candidates=1), "depth-one")
    collector = _RetainedLaneCollector(budget)
    lanes, qualifications = _generate_candidate_lanes(computed, budget, collector)
    assert (
        sum(map(len, lanes.values())) == collector.retained_count == 1
        and qualifications == ()
        and budget.candidates == 0
    )
    collector.schedule()
    assert budget.candidates == 1
    assert (
        collector.exhaustion()
        == "optimization depth-one generated transitions budget exhausted (measured 2, configured 1)"  # noqa: E501
    )
    transition = _optimization_result(
        goal_request(request),
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), proofs=0),
        analyzer=analyze_retained,
    )
    final = _optimization_result(
        goal_request(request),
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), final_proofs=0),
        analyzer=analyze_retained,
    )
    assert transition.search_scope.qualifications == (
        "optimization depth-one proof steps budget exhausted (measured 1, configured 0)",
    )
    assert final.search_scope.qualifications == (
        "optimization final-acceptance proof steps budget exhausted (measured 1, configured 0)",
    )


@pytest.mark.parametrize(
    ("field", "qualification"),
    [
        (
            "inspections",
            "optimization depth-one inspected nodes budget exhausted (measured 9, configured 0)",
        ),
        (
            "depth_two_inspections",
            "optimization depth-two inspected nodes budget exhausted (measured 5, configured 0)",
        ),
        (
            "whole_inspections",
            "optimization whole-request inspected nodes budget exhausted (measured 9, configured 0)",  # noqa: E501
        ),
        (
            "candidates",
            "optimization depth-one generated transitions budget exhausted (measured 1, configured 0)",  # noqa: E501
        ),
        (
            "complete_reanalyses",
            "optimization depth-one complete candidate reanalyses budget exhausted (measured 1, configured 0)",  # noqa: E501
        ),
        (
            "expanded_parents",
            "optimization depth-two expanded parents budget exhausted (measured 1, configured 0)",
        ),
        (
            "retained_states",
            "optimization depth-one retained states budget exhausted (measured 1, configured 0)",
        ),
        (
            "aggregate_transform_nodes",
            "optimization depth-one aggregate transformation nodes budget exhausted (measured 7, configured 0)",  # noqa: E501
        ),
        (
            "proofs",
            "optimization depth-one proof steps budget exhausted (measured 1, configured 0)",
        ),
        (
            "proof_nodes",
            "optimization depth-one proof nodes budget exhausted (measured 14, configured 0)",
        ),
        (
            "work_nodes",
            "optimization depth-one work-comparison nodes budget exhausted (measured 2, configured 0)",  # noqa: E501
        ),
        (
            "whole_proofs",
            "optimization whole-request proof steps budget exhausted (measured 1, configured 0)",
        ),
        (
            "whole_proof_nodes",
            "optimization whole-request proof nodes budget exhausted (measured 14, configured 0)",
        ),
        (
            "whole_work_nodes",
            "optimization whole-request work-comparison nodes budget exhausted (measured 2, configured 0)",  # noqa: E501
        ),
        (
            "final_states",
            "optimization final-acceptance retained states budget exhausted (measured 1, configured 0)",  # noqa: E501
        ),
        (
            "final_proofs",
            "optimization final-acceptance proof steps budget exhausted (measured 1, configured 0)",
        ),
        (
            "final_proof_nodes",
            "optimization final-acceptance proof nodes budget exhausted (measured 14, configured 0)",  # noqa: E501
        ),
        (
            "final_work_nodes",
            "optimization final-acceptance work-comparison nodes budget exhausted (measured 2, configured 0)",  # noqa: E501
        ),
    ],
)
def test_composed_search_v1_every_injected_counter_is_independently_qualified(
    field: str, qualification: str
) -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import _optimization_result, _OptimizationBudgetConfig

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0")
    computed = analyze_retained(request)
    assert not isinstance(computed, AnalysisFailure)
    result = _optimization_result(
        goal_request(request),
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), **{field: 0}),
        analyzer=analyze_retained,
    )
    assert result.search_scope.completion == "incomplete"
    assert qualification in result.search_scope.qualifications
