# pyright: reportPrivateUsage=false
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_advice_has_a_separate_result_allowance_and_excludes_its_key_from_base() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service

    assert formula_service.MAX_RESULT_BYTES == 262_144
    assert formula_service.MAX_OPTIMIZATION_BYTES == 262_144
    assert formula_service.MAX_COMBINED_RESULT_BYTES == 524_288
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    assert outcome.status == "success" and outcome.optimization is not None
    base_json = outcome.model_dump_json(exclude={"optimization"})
    assert '"optimization"' not in base_json
    assert len(outcome.optimization.model_dump_json().encode("utf-8")) < 65_536


def test_candidate_budget_exhaustion_preserves_already_proved_advice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._optimization import budgets as budget_owner

    monkeypatch.setattr(budget_owner, "MAX_OPTIMIZATION_CANDIDATES", 1)
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 0) * (y + 0)",
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.optimization.status == "incomplete"
    assert outcome.optimization.qualifications == (
        "optimization depth-one generated transitions budget exhausted (measured 2, configured 1)",
    )
    assert len(outcome.optimization.suggestions) == 1


def test_historical_exact_base_result_limit_still_succeeds() -> None:
    from py_science.formula import AnalysisSuccess
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation, OperationCounts, ScenarioResult

    def outcome_with_padding(length: int) -> AnalysisSuccess:
        return AnalysisSuccess(
            interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
            operation_counts=OperationCounts(
                additions=0,
                subtractions=0,
                multiplications=0,
                divisions=0,
                powers=0,
            ),
            abstract_work=0,
            scenarios=(
                ScenarioResult(
                    name="padding",
                    substituted_work="0",
                    qualifications=("x" * length,),
                ),
            ),
        )

    empty = outcome_with_padding(0)
    overhead = len(empty.model_dump_json(exclude={"optimization"}).encode("utf-8"))
    exact = outcome_with_padding(formula_service.MAX_RESULT_BYTES - overhead)
    assert (
        len(exact.model_dump_json(exclude={"optimization"}).encode("utf-8"))
        == formula_service.MAX_RESULT_BYTES
    )
    assert formula_service._bound_result(exact).status == "success"  # pyright: ignore[reportPrivateUsage]
    overflow = outcome_with_padding(formula_service.MAX_RESULT_BYTES - overhead + 1)
    assert formula_service._bound_result(overflow).status == "failure"  # pyright: ignore[reportPrivateUsage]


def test_oversized_advice_truncates_without_replacing_base_success() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = outcome.optimization.suggestions[0]
    oversized = suggestion.model_copy(
        update={
            "transformations": (
                suggestion.transformations[0].model_copy(
                    update={
                        "proposed": Interpretation(
                            normalized_sympy="x" * 140_000, normalized_latex="x" * 140_000
                        )
                    }
                ),
            )
        }
    )
    bounded = formula_service._bound_result(  # pyright: ignore[reportPrivateUsage]
        outcome.model_copy(
            update={
                "optimization": outcome.optimization.model_copy(
                    update={"suggestions": (oversized,)}
                )
            }
        )
    )
    assert bounded.status == "success"
    assert bounded.optimization.status == outcome.optimization.status
    assert bounded.optimization.suggestions == ()
    assert bounded.optimization.projection_status == "truncated"
    assert bounded.optimization.projection_qualifications[0].startswith(
        "optimization advice bytes budget exhausted (measured "
    )
    assert "configured 262144" in bounded.optimization.projection_qualifications[0]


def test_exact_base_and_maximum_field_contribution_preserve_success() -> None:
    from py_science.formula import AnalysisSuccess
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation, OperationCounts, ScenarioResult

    empty = AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
        operation_counts=OperationCounts(),
        abstract_work=0,
        scenarios=(ScenarioResult(name="padding", substituted_work="0", qualifications=("",)),),
    )
    base_overhead = len(empty.model_dump_json(exclude={"optimization"}).encode("utf-8"))
    exact_base = empty.model_copy(
        update={
            "scenarios": (
                empty.scenarios[0].model_copy(
                    update={
                        "qualifications": (
                            "x" * (formula_service.MAX_RESULT_BYTES - base_overhead),
                        )
                    }
                ),
            )
        }
    )
    assert (
        len(exact_base.model_dump_json(exclude={"optimization"}).encode("utf-8"))
        == formula_service.MAX_RESULT_BYTES
    )

    seed = exact_base.optimization.model_copy(
        update={"status": "incomplete", "qualifications": ("",)}
    )
    seed_bytes = len(seed.model_dump_json().encode("utf-8"))
    maximum_report = seed.model_copy(
        update={"qualifications": ("y" * (formula_service.MAX_OPTIMIZATION_BYTES - seed_bytes),)}
    )
    assert (
        len(maximum_report.model_dump_json().encode("utf-8"))
        == formula_service.MAX_OPTIMIZATION_BYTES
    )
    combined = exact_base.model_copy(update={"optimization": maximum_report})
    field_contribution = len(combined.model_dump_json().encode("utf-8")) - len(
        combined.model_dump_json(exclude={"optimization"}).encode("utf-8")
    )
    assert field_contribution > formula_service.MAX_OPTIMIZATION_BYTES

    bounded = formula_service._bound_result(combined)  # pyright: ignore[reportPrivateUsage]
    assert bounded.status == "success"
    assert bounded.optimization.status == "incomplete"
    assert bounded.optimization.qualifications == (
        "optimization search qualifications truncated by output projection",
    )
    assert bounded.optimization.projection_status == "truncated"
    assert bounded.optimization.projection_qualifications == (
        "optimization advice bytes budget exhausted",
    )


def test_independent_budget_qualifications_report_measured_and_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._optimization import budgets as budget_owner

    monkeypatch.setattr(budget_owner, "MAX_OPTIMIZATION_CANDIDATES", 1)
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)"))
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.optimization.status == "incomplete"
    qualification = outcome.optimization.qualifications[0]
    assert "generated transitions" in qualification
    assert "measured 2" in qualification
    assert "configured 1" in qualification
    assert outcome.optimization.suggestions


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
        analyze,
    )
    from py_science.formula.expressions import ExpressionTooComplex

    def exhausted(*_args: object, **_kwargs: object) -> object:
        raise ExpressionTooComplex("bounded substitution exhausted")

    from py_science.formula._optimization.families import cross_equation_sharing

    monkeypatch.setattr(cross_equation_sharing, "substitute", exhausted)
    outcome = analyze(
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

    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.optimization.status == "incomplete"
    assert any(
        "optimization per-candidate transformation nodes budget exhausted" in item
        for item in outcome.optimization.qualifications
    )


def test_recursive_horner_inspection_is_charged_before_backend_descent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._optimization import budgets as budget_owner
    from py_science.formula.expressions import expression_node_count

    expression = "2*x**3 + 3*x**2 + 4*x + 5"
    initial_nodes = expression_node_count(_expression(expression))
    monkeypatch.setattr(budget_owner, "MAX_OPTIMIZATION_INSPECTIONS", initial_nodes)

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))

    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.interpretation.normalized_sympy == "4*x + 5 + 3*x**2 + 2*x**3"
    assert outcome.optimization.status == "incomplete"
    assert any(
        item
        == (
            "optimization depth-one inspected nodes budget exhausted "
            f"(measured {initial_nodes * 2}, configured {initial_nodes})"
        )
        for item in outcome.optimization.qualifications
    )


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
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    configured: int,
    resource: str,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._optimization import budgets as budget_owner

    monkeypatch.setattr(budget_owner, constant, configured)
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)"))
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.interpretation.normalized_sympy == "x*y"
    assert outcome.optimization.status == "incomplete"
    assert any(resource in item for item in outcome.optimization.qualifications)
    assert all(
        "measured" in item and "configured" in item for item in outcome.optimization.qualifications
    )


def test_multibyte_advice_limit_measures_encoded_bytes() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = outcome.optimization.suggestions[0]
    oversized = suggestion.model_copy(
        update={
            "transformations": (
                suggestion.transformations[0].model_copy(
                    update={
                        "proposed": Interpretation(
                            normalized_sympy="é" * 140_000, normalized_latex="é" * 140_000
                        )
                    }
                ),
            )
        }
    )
    bounded = formula_service._bound_result(  # pyright: ignore[reportPrivateUsage]
        outcome.model_copy(
            update={
                "optimization": outcome.optimization.model_copy(
                    update={"suggestions": (oversized,)}
                )
            }
        )
    )
    assert bounded.status == "success" and bounded.optimization is not None
    assert bounded.optimization.projection_status == "truncated"
    qualification = bounded.optimization.projection_qualifications[0]
    assert "advice bytes" in qualification
    assert "measured" in qualification and "configured 262144" in qualification


def test_optimize_result_bound_keeps_every_plan_that_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        FormulaSyntax,
        OptimizationSuccess,
        OptimizeRequest,
        optimize,
        service,
    )

    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(alpha + beta)*(alpha + beta) + 0",
            max_plans=16,
        )
    )
    assert isinstance(result, OptimizationSuccess)
    assert len(result.plans) >= 2
    oversized = result.model_copy(
        update={"search_status": "incomplete", "qualifications": ("x" * 10_000,)}
    )
    monkeypatch.setattr(service, "MAX_OPTIMIZATION_BYTES", 30_000)

    bounded = service._bound_optimization_result(oversized)

    assert bounded.search_status == "incomplete"
    assert bounded.projection_status == "complete"
    assert len(bounded.plans) == len(result.plans)
    assert len(bounded.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_optimize_result_bound_keeps_largest_fitting_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        FormulaSyntax,
        OptimizationSuccess,
        OptimizeRequest,
        optimize,
        service,
    )

    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(alpha + beta)*(alpha + beta) + 0",
            max_plans=16,
        )
    )
    assert isinstance(result, OptimizationSuccess)
    assert len(result.plans) >= 2
    oversized = result.model_copy(
        update={"search_status": "incomplete", "qualifications": ("x" * 10_000,)}
    )
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 12_000)

    bounded = service._bound_optimization_result(oversized)

    assert bounded.projection_status == "truncated"
    assert len(bounded.plans) < len(result.plans)
    assert len(bounded.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_optimize_result_bound_handles_oversized_empty_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import OptimizationSuccess, service

    oversized = OptimizationSuccess(
        requested_limit=3,
        search_status="incomplete",
        qualifications=("x" * 4_000,),
    )
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 5_000)

    bounded = service._bound_optimization_result(oversized)

    assert bounded.plans == ()
    assert bounded.search_status == "incomplete"
    assert len(bounded.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_optimize_operation_bounds_duplicated_plan_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        FormulaSyntax,
        OptimizationSuccess,
        OptimizeRequest,
        optimize,
        service,
    )
    from py_science.formula._service import result_bounds

    monkeypatch.setattr(result_bounds, "MAX_OPTIMIZATION_BYTES", 600)
    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(alpha + beta)*(alpha + beta) + 0",
            max_plans=16,
        )
    )

    assert isinstance(result, OptimizationSuccess)
    assert result.search_status == "complete"
    assert result.projection_status == "truncated"
    assert result.projection_qualifications
    assert len(result.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_composed_search_v1_budget_seams_distinguish_transition_and_final_proofs() -> None:
    """The injected counters qualify the owning search phase, not a generic budget."""
    from dataclasses import replace

    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import (
        _generate_candidate_lanes,
        _optimization_report,
        _OptimizationBudget,
        _OptimizationBudgetConfig,
        _RetainedLaneCollector,
    )

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0")
    computed = analyze_retained(request)
    assert not isinstance(computed, AnalysisFailure)
    materialization_budget = _OptimizationBudget(
        replace(_OptimizationBudgetConfig(), candidates=1), "depth-one"
    )
    collector = _RetainedLaneCollector(materialization_budget)
    lanes, qualifications = _generate_candidate_lanes(computed, materialization_budget, collector)
    assert sum(map(len, lanes.values())) == collector.retained_count == 1
    # Discovery retains descriptors only.  The selected fair prefix is the
    # sole point that enters a factory and consumes a generated transition.
    assert materialization_budget.candidates == 0
    assert qualifications == ()
    collector.schedule()
    assert materialization_budget.candidates == 1
    assert collector.exhaustion() == (
        "optimization depth-one generated transitions budget exhausted (measured 2, configured 1)"
    )

    transition = _optimization_report(
        request,
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), proofs=0),
        analyzer=analyze_retained,
    )
    final = _optimization_report(
        request,
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), final_proofs=0),
        analyzer=analyze_retained,
    )

    assert transition.status == final.status == "incomplete"
    assert transition.qualifications == (
        "optimization depth-one proof steps budget exhausted (measured 1, configured 0)",
    )
    assert final.qualifications == (
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
            "optimization whole-request inspected nodes budget exhausted "
            "(measured 9, configured 0)",
        ),
        (
            "candidates",
            "optimization depth-one generated transitions budget exhausted "
            "(measured 1, configured 0)",
        ),
        (
            "complete_reanalyses",
            "optimization depth-one complete candidate reanalyses budget exhausted "
            "(measured 1, configured 0)",
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
            "optimization depth-one aggregate transformation nodes budget exhausted "
            "(measured 7, configured 0)",
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
            "optimization depth-one work-comparison nodes budget exhausted "
            "(measured 2, configured 0)",
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
            "optimization whole-request work-comparison nodes budget exhausted "
            "(measured 2, configured 0)",
        ),
        (
            "final_states",
            "optimization final-acceptance retained states budget exhausted "
            "(measured 1, configured 0)",
        ),
        (
            "final_proofs",
            "optimization final-acceptance proof steps budget exhausted (measured 1, configured 0)",
        ),
        (
            "final_proof_nodes",
            "optimization final-acceptance proof nodes budget exhausted "
            "(measured 14, configured 0)",
        ),
        (
            "final_work_nodes",
            "optimization final-acceptance work-comparison nodes budget exhausted "
            "(measured 2, configured 0)",
        ),
    ],
)
def test_composed_search_v1_every_injected_counter_is_independently_qualified(
    field: str, qualification: str
) -> None:
    """Every fixed depth, whole-request, and final counter owns its diagnostic."""
    from dataclasses import replace

    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import _optimization_report, _OptimizationBudgetConfig

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0")
    computed = analyze_retained(request)
    assert not isinstance(computed, AnalysisFailure)
    configuration = replace(_OptimizationBudgetConfig(), **{field: 0})

    report = _optimization_report(
        request, computed, computed.work_context, configuration, analyzer=analyze_retained
    )

    assert report.status == "incomplete"
    assert qualification in report.qualifications
