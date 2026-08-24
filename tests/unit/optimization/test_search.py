# pyright: reportPrivateUsage=false
from typing import Any, cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_analysis_request_rejects_the_former_optimization_key() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as error:
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": "x",
                "optimization": {"max_suggestions": 0},
            }
        )
    assert error.value.errors()[0]["loc"] == ("optimization",)


def test_ordinary_analysis_has_no_optimization_serialization_or_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._service import optimization as optimization_service

    calls = 0
    original = optimization_service._optimization_result

    def counted_optimization(*args: Any, **kwargs: Any):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(optimization_service, "_optimization_result", counted_optimization)
    computation = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="(x + 1) * (x + 1)"
    )
    ordinary = analyze(computation)
    assert ordinary.status == "success"
    assert "optimization" not in ordinary.model_dump()
    assert calls == 0

    explicit = optimize_analysis(computation, projection_limit=16)
    assert explicit.status == "success"
    assert explicit.plans
    assert calls == 1


def test_optimize_request_rejects_former_passive_controls() -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizeRequest
    from pydantic import ValidationError

    request = goal_request(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    for former in (
        {"max_plans": 1},
        {"objective": {"kind": "unit_work_v1"}},
        {"enabled_algorithmic_families": ["finite_polynomial_sum_v1"]},
    ):
        with pytest.raises(ValidationError) as error:
            OptimizeRequest.model_validate({**request.model_dump(), **former})
        assert error.value.errors()[0]["loc"] == tuple(former)


def test_composed_search_v1_max_plans_is_an_exact_ranked_prefix() -> None:
    """Changing the projection limit neither changes nor reruns the search population."""
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    def plans(limit: int):
        outcome = optimize_analysis(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0"
            ),
            projection_limit=limit,
        )
        assert outcome.status == "success"
        return outcome.plans

    full = plans(16)
    assert len(full) >= 2
    assert plans(1) == full[:1]
    assert plans(2) == full[:2]


def test_composed_search_v1_retained_lanes_are_round_robin_and_order_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bounded depth population is independent of family and emission order."""
    from dataclasses import replace

    from goal_requests import goal_request
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization import search as search_owner
    from py_science.formula.optimization import (
        _CandidateComputation,
        _CandidateDescriptor,
        _optimization_result,
        _OptimizationBudget,
        _OptimizationBudgetConfig,
        _RetainedLaneCollector,
    )

    families = tuple(reversed(search_owner._FAMILY_ORDER[:3]))

    def proposal(kind: str, value: int) -> _CandidateComputation:
        expression = _expression(f"x + {value}")
        return _CandidateComputation(
            kind=cast("object", kind),  # type: ignore[arg-type]
            target="expression",
            original=expression,
            proposed=_expression("x"),
            occurrences=(),
        )

    def collect(reverse_families: bool, reverse_descriptors: bool):
        calls: list[tuple[str, int]] = []
        budget = _OptimizationBudget(replace(_OptimizationBudgetConfig(), candidates=1))
        collector = _RetainedLaneCollector(budget)
        ordered_families = tuple(reversed(families)) if reverse_families else families
        for family in ordered_families:
            values = tuple(reversed(range(4))) if reverse_descriptors else range(4)
            for value in values:
                candidate = proposal(family, value)
                collector.add(
                    (family,),
                    _CandidateDescriptor(
                        kind=cast("object", family),  # type: ignore[arg-type]
                        sort_key=(family, value),
                        factory=lambda candidate=candidate, family=family, value=value: (
                            calls.append((family, value)) or candidate
                        ),
                    ),
                )
        selected = collector.schedule()
        return selected, calls, budget, collector

    baseline, calls, budget, collector = collect(False, False)
    reversed_population, reversed_calls, reversed_budget, reversed_collector = collect(True, True)
    assert baseline == reversed_population
    assert calls == reversed_calls == [(families[0], 0)]
    assert budget.candidates == reversed_budget.candidates == 1
    assert collector.retained_count == reversed_collector.retained_count == 1
    assert (
        collector.exhaustion()
        == reversed_collector.exhaustion()
        == (
            "optimization transition generated transitions budget exhausted "
            "(measured 2, configured 1)"
        )
    )

    computation = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y + 0)"
    )
    request = goal_request(computation)
    computed = analyze_retained(computation)
    assert not isinstance(computed, AnalysisFailure)
    seam = replace(_OptimizationBudgetConfig(), candidates=2, complete_reanalyses=2)
    baseline = _optimization_result(
        request, computed, computed.work_context, seam, analyzer=analyze_retained
    )
    original_order = search_owner._FAMILY_ORDER
    patched_order = tuple(reversed(original_order))
    monkeypatch.setattr(search_owner, "_FAMILY_ORDER", patched_order)
    reversed_families = _optimization_result(
        request, computed, computed.work_context, seam, analyzer=analyze_retained
    )
    # The public result reports the patched lane order, but the all-lane
    # search population and every replayed plan remain exactly invariant.
    def normalized_families(result: object):
        typed = cast("Any", result)
        families = baseline.search_scope.families
        return typed.model_copy(
            update={
                "search_scope": typed.search_scope.model_copy(update={"families": families}),
                "plans": tuple(
                    plan.model_copy(
                        update={"claim": plan.claim.model_copy(update={"families": families})}
                    )
                    for plan in typed.plans
                ),
            }
        )

    assert set(baseline.search_scope.families) == set(original_order)
    assert set(reversed_families.search_scope.families) == set(original_order)
    assert normalized_families(reversed_families) == baseline
    monkeypatch.undo()
    assert original_order == search_owner._FAMILY_ORDER


def test_private_accounting_records_observed_rejections_without_extra_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accounting observes the existing schedule; it never changes it or reruns it."""
    from goal_requests import goal_request
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization import search as search_owner
    from py_science.formula._optimization.diagnostics import _OutcomeAccounting

    computation = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="f(x) + f(x)")
    request = goal_request(computation)
    computed = analyze_retained(computation)
    assert not isinstance(computed, AnalysisFailure)
    accounting = _OutcomeAccounting()
    calls = {"generation": 0, "verification": 0}
    generate = search_owner._generate_candidate_lanes
    verify = search_owner._verify_candidate

    def counted_generation(*args: Any, **kwargs: Any):
        calls["generation"] += 1
        return generate(*args, **kwargs)

    def counted_verification(*args: Any, **kwargs: Any):
        calls["verification"] += 1
        return verify(*args, **kwargs)

    monkeypatch.setattr(search_owner, "_generate_candidate_lanes", counted_generation)
    monkeypatch.setattr(search_owner, "_verify_candidate", counted_verification)
    result = search_owner._optimization_result(
        request, computed, computed.work_context, analyzer=analyze_retained, accounting=accounting
    )

    assert result.model_dump() == search_owner._optimization_result(
        request, computed, computed.work_context, analyzer=analyze_retained
    ).model_dump()
    assert calls == {"generation": 2, "verification": 2}
    assert accounting.generation_events == 1
    assert accounting.proposals == accounting.transition_verifications == 1
    assert accounting.rejected_before_final_acceptance == 1
    assert accounting.final_acceptance_attempts == 0
    assert accounting.blockers[0].reason == "missing_primitive_cost"
    assert accounting.blockers[0].family == "repeated_call"
    assert accounting.blockers[0].target == "expression"


def test_private_accounting_distinguishes_empty_and_nonpositive_outcomes() -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization.diagnostics import _OutcomeAccounting
    from py_science.formula._optimization.search import _optimization_result

    def observe(expression: str) -> _OutcomeAccounting:
        computation = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)
        request = goal_request(computation)
        computed = analyze_retained(computation)
        assert not isinstance(computed, AnalysisFailure)
        accounting = _OutcomeAccounting()
        _optimization_result(
            request,
            computed,
            computed.work_context,
            analyzer=analyze_retained,
            accounting=accounting,
        )
        return accounting

    empty = observe("x")
    nonpositive = observe("Sum(x*x + i, (i, 0, 0))")
    assert (
        empty.proposals,
        empty.transition_verifications,
        empty.rejected_before_final_acceptance,
    ) == (0, 0, 0)
    assert (
        nonpositive.proposals,
        nonpositive.transition_verifications,
        nonpositive.rejected_before_final_acceptance,
    ) == (1, 1, 1)
    assert not empty.blockers and not nonpositive.blockers


def test_private_accounting_omits_unrelated_unresolved_assumptions() -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisFailure, AnalysisRequest, Assumption, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization.diagnostics import _OutcomeAccounting
    from py_science.formula._optimization.search import _optimization_result

    computation = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1) * (x + 1)",
        assumptions=(Assumption(name="positive", relationship="x > 0"),),
    )
    request = goal_request(computation)
    computed = analyze_retained(computation)
    assert not isinstance(computed, AnalysisFailure)
    accounting = _OutcomeAccounting()

    _optimization_result(
        request, computed, computed.work_context, analyzer=analyze_retained, accounting=accounting
    )

    assert accounting.proposals == accounting.transition_verifications == 1
    assert accounting.rejected_before_final_acceptance == 1
    assert not accounting.blockers


def test_private_accounting_records_target_local_cardinality_fact() -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization.diagnostics import _OutcomeAccounting
    from py_science.formula._optimization.search import _optimization_result

    computation = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum((x + 1) * (x + 1), (i, a, b))",
    )
    request = goal_request(computation)
    computed = analyze_retained(computation)
    assert not isinstance(computed, AnalysisFailure)
    accounting = _OutcomeAccounting()

    result = _optimization_result(
        request, computed, computed.work_context, analyzer=analyze_retained, accounting=accounting
    )

    assert result == _optimization_result(
        request, computed, computed.work_context, analyzer=analyze_retained
    )
    assert any(
        blocker.reason == "unproved_domain_or_cardinality"
        and blocker.family == "repeated_subexpression"
        and blocker.target == "expression"
        for blocker in accounting.blockers
    )


def test_private_accounting_omits_unknown_cost_from_another_system_output() -> None:
    from goal_requests import goal_request
    from py_science.formula import (
        AnalysisFailure,
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        VariableDeclaration,
    )
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization.diagnostics import _OutcomeAccounting
    from py_science.formula._optimization.search import _optimization_result

    computation = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(
            EquationRequest(name="target", expression="Eq(target, x*y + x*z)"),
            EquationRequest(name="other", expression="Eq(other, opaque(x))"),
        ),
        variables={
            name: VariableDeclaration(domain=MathematicalDomain.REAL)
            for name in ("x", "y", "z")
        },
    )
    request = goal_request(computation)
    computed = analyze_retained(computation)
    assert not isinstance(computed, AnalysisFailure)
    accounting = _OutcomeAccounting()

    _optimization_result(
        request, computed, computed.work_context, analyzer=analyze_retained, accounting=accounting
    )

    assert accounting.proposals == accounting.transition_verifications == 1
    assert accounting.rejected_before_final_acceptance == 1
    assert not accounting.blockers
