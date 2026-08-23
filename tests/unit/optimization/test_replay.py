# pyright: reportPrivateUsage=false
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_retained_analysis_disables_optimization() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained

    retained = analyze_retained(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))

    assert not isinstance(retained, AnalysisFailure)
    assert retained.success.optimization.model_dump() == {
        "requested_limit": 0,
        "status": "disabled",
        "suggestions": (),
        "plans": (),
        "qualifications": (),
        "projection_status": "complete",
        "projection_qualifications": (),
    }
    assert (
        type(retained.success).model_validate_json(retained.success.model_dump_json()).optimization
        == retained.success.optimization
    )


def test_complete_candidate_replays_expression_local_reuse_and_neutral_removal() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import (
        _complete_candidate,
        _generate_candidates,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1) * (x + 1) + 0",
    )
    retained = analyze_retained(request)
    assert not isinstance(retained, AnalysisFailure)
    candidates, _ = _generate_candidates(retained, _OptimizationBudget())
    for candidate in candidates:
        if candidate.kind not in {"repeated_subexpression", "redundant_operation_removal"}:
            continue
        replayed = analyze_retained(_complete_candidate(candidate, request, retained))
        assert not isinstance(replayed, AnalysisFailure)
        assert replayed.expression is not None
        assert replayed.aggregate_analysis.total_work != retained.aggregate_analysis.total_work


def test_complete_candidate_schedule_preserves_all_kinds_and_the_tail() -> None:
    from py_science.formula.optimization import (
        _CandidateComputation,
        _complete_candidate_schedule,
    )

    kinds = (
        "repeated_subexpression",
        "repeated_call",
        "reciprocal_reuse",
        "factoring",
        "redundant_operation_removal",
        "iterator_invariant_hoisting",
        "cross_equation_sharing",
        "horner",
        "repeated_subexpression",
    )
    candidates = tuple(
        _CandidateComputation(
            kind=kind,
            target=f"target{position}",
            original=_expression("x"),
            proposed=_expression("x"),
            occurrences=(),
        )
        for position, kind in enumerate(kinds)
    )

    scheduled = _complete_candidate_schedule(candidates)

    assert len(scheduled) == 8
    assert {item.kind for item in scheduled} == set(kinds)
    assert scheduled[-1] is candidates[-1]


def test_ordinary_analysis_optimization_ownership() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    default = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    disabled = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + 0",
            optimization=OptimizationConfig(max_suggestions=0),
        )
    )

    assert default.status == "success"
    assert default.optimization.requested_limit == 3
    assert default.optimization.status == "complete"
    assert any(
        suggestion.kind == "redundant_operation_removal"
        for suggestion in default.optimization.suggestions
    )
    assert disabled.status == "success"
    assert disabled.optimization.model_dump() == {
        "requested_limit": 0,
        "status": "disabled",
        "suggestions": (),
        "plans": (),
        "qualifications": (),
        "projection_status": "complete",
        "projection_qualifications": (),
    }


def test_optimize_operation_returns_replayable_complete_plans() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizeRequest,
        analyze,
        optimize,
    )

    request = OptimizeRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x*x + x*x",
    )
    result = optimize(request)

    assert result.status == "success"
    assert result.requested_limit == 3
    assert result.plans
    plan = result.plans[0]
    assert plan.candidate.syntax == FormulaSyntax.SYMPY
    assert plan.candidate.expression is not None
    assert plan.candidate.outputs == ("expression",)
    replay = analyze(AnalysisRequest.model_validate(plan.candidate.model_dump()))
    assert replay.status == "success"


def test_analysis_replay_rejects_invalid_output_identities() -> None:
    from py_science.formula import AnalysisRequest, EquationRequest, FormulaSyntax
    from pydantic import ValidationError

    equation = EquationRequest(name="a", expression="Eq(a, x)")
    payloads = (
        {"syntax": FormulaSyntax.SYMPY, "expression": "x", "outputs": ("wrong",)},
        {
            "syntax": FormulaSyntax.SYMPY,
            "equations": (equation,),
            "outputs": ("missing",),
        },
        {
            "syntax": FormulaSyntax.SYMPY,
            "equations": (equation,),
            "outputs": ("a", "a"),
        },
    )
    for payload in payloads:
        with pytest.raises(ValidationError, match="output identit"):
            AnalysisRequest.model_validate(payload)


def test_optimize_system_plan_outputs_exclude_generated_producers() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        OptimizationSuccess,
        OptimizeRequest,
        VariableDeclaration,
        analyze,
        optimize,
    )

    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="a", expression="Eq(a, x*x + 1)"),
                EquationRequest(name="b", expression="Eq(b, x*x - 1)"),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            max_plans=16,
        )
    )

    assert isinstance(result, OptimizationSuccess)
    sharing = next(
        plan for plan in result.plans if plan.suggestion.kind == "cross_equation_sharing"
    )
    assert sharing.candidate.outputs == ("a", "b")
    assert {equation.name for equation in sharing.candidate.equations} == {
        "optimization_tmp_1",
        "a",
        "b",
    }
    replay = analyze(AnalysisRequest.model_validate(sharing.candidate.model_dump()))
    assert replay.status == "success"


def test_composed_search_v1_emits_replayable_trace() -> None:
    """A composed plan is represented by replayable parent-relative steps."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0"))
    assert outcome.status == "success"
    # Protocol v15 replaces the former single-family suggestion payload.
    assert any(len(plan.trace) == 2 for plan in outcome.optimization.plans)


def test_composed_search_v1_trace_objectives_are_continuous_and_replayable() -> None:
    """Every local transition connects its parent objective to the final proof."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0"))
    assert outcome.status == "success" and outcome.optimization is not None
    plan = next(item for item in outcome.optimization.plans if len(item.trace) == 2)

    assert plan.trace[0].objective_before == plan.suggestion.objective_before
    assert plan.trace[-1].objective_after == plan.suggestion.objective_after
    assert plan.trace[0].objective_after == plan.trace[1].objective_before
    assert plan.trace[-1].candidate == plan.candidate
    for step in plan.trace:
        replayed = analyze(AnalysisRequest.model_validate(step.candidate.model_dump()))
        assert replayed.status == "success"


def test_neutral_analyzer_is_explicit_and_has_no_service_or_registry_edge() -> None:
    """Replay callers receive the neutral analyzer without process-global setup."""
    from pathlib import Path

    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import _optimization_report
    from py_science.formula.service import _analyze_computation

    optimization_source = Path(_optimization_report.__code__.co_filename).read_text()
    formula_directory = Path(analyze_retained.__code__.co_filename).parents[1]
    comparison_source = formula_directory.joinpath("comparison.py").read_text()
    service_source = formula_directory.joinpath("service.py").read_text()

    assert _analyze_computation is analyze_retained
    assert "_retained_analyzer" not in optimization_source
    assert "_configure_retained_analyzer" not in optimization_source
    assert "py_science.formula.service" not in optimization_source
    assert "py_science.formula._analysis.computation" in comparison_source
    assert "py_science.formula._analysis.computation" in service_source
