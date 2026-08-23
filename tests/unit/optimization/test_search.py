# pyright: reportPrivateUsage=false
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_optimization_config_is_strict_and_bounded() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    default = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x")
    disabled = AnalysisRequest.model_validate(
        {
            "syntax": FormulaSyntax.SYMPY,
            "expression": "x",
            "optimization": {"max_suggestions": 0},
        }
    )
    assert default.optimization.max_suggestions == 3
    assert disabled.optimization.max_suggestions == 0
    with pytest.raises(ValidationError) as error:
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": "x",
                "optimization": {"max_suggestions": 17},
            }
        )
    assert error.value.errors()[0]["loc"] == ("optimization", "max_suggestions")


def test_disabled_optimization_preserves_every_ordinary_field() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    enabled = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1) * (x + 1)"))
    disabled = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1) * (x + 1)",
            optimization=OptimizationConfig(max_suggestions=0),
        )
    )
    assert enabled.status == "success" and disabled.status == "success"
    assert enabled.model_copy(update={"optimization": None}) == disabled.model_copy(
        update={"optimization": None}
    )
    assert disabled.optimization is not None
    assert disabled.optimization.status == "disabled"


def test_optimization_config_truth_table_and_exact_error_paths() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    base = {"syntax": FormulaSyntax.SYMPY, "expression": "x"}
    assert AnalysisRequest.model_validate(base).optimization.max_suggestions == 3
    for accepted in (0, 16):
        assert (
            AnalysisRequest.model_validate(
                {**base, "optimization": {"max_suggestions": accepted}}
            ).optimization.max_suggestions
            == accepted
        )
    for rejected in (-1, 17, 1.5, "3"):
        with pytest.raises(ValidationError) as error:
            AnalysisRequest.model_validate({**base, "optimization": {"max_suggestions": rejected}})
        assert error.value.errors()[0]["loc"] == (
            "optimization",
            "max_suggestions",
        )
    with pytest.raises(ValidationError) as error:
        AnalysisRequest.model_validate(
            {**base, "optimization": {"max_suggestions": 3, "extra": True}}
        )
    assert error.value.errors()[0]["loc"] == ("optimization", "extra")


def test_composed_search_v1_max_plans_is_an_exact_ranked_prefix() -> None:
    """Changing the output limit neither changes nor reruns the search population."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    def plans(limit: int):
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="(x + 1)*(x + 1) + 0",
                optimization=OptimizationConfig(max_suggestions=limit),
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        return outcome.optimization.plans

    full = plans(16)
    assert len(full) >= 2
    assert plans(1) == full[:1]
    assert plans(2) == full[:2]


def test_composed_search_v1_retained_lanes_are_round_robin_and_order_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bounded depth population is independent of family and emission order."""
    from dataclasses import replace

    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula import optimization as optimization_service
    from py_science.formula.optimization import (
        _CandidateComputation,
        _CandidateDescriptor,
        _optimization_report,
        _OptimizationBudget,
        _OptimizationBudgetConfig,
        _RetainedLaneCollector,
    )
    from py_science.formula.service import _analyze_computation

    families = tuple(reversed(optimization_service._FAMILY_ORDER[:3]))

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

    # Family registration and descriptor emission do not choose the bounded
    # population.  Only the selected fair prefix constructs a candidate.
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

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y + 0)")
    computed = _analyze_computation(request)
    assert not isinstance(computed, AnalysisFailure)
    seam = replace(_OptimizationBudgetConfig(), candidates=2, complete_reanalyses=2)
    baseline = _optimization_report(request, computed, computed.work_context, seam)
    monkeypatch.setattr(
        optimization_service, "_FAMILY_ORDER", tuple(reversed(optimization_service._FAMILY_ORDER))
    )
    reversed_families = _optimization_report(request, computed, computed.work_context, seam)
    assert reversed_families == baseline
