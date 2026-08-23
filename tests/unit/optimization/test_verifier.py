# pyright: reportPrivateUsage=false
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_optimization_suggestion_rejects_invalid_zero_or_negative_work() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from pydantic import ValidationError

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * y + x * z"))
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = outcome.optimization.suggestions[0]
    zero_post_work = type(suggestion).model_validate(
        {
            **suggestion.model_dump(),
            "objective_before": "1",
            "objective_after": "0",
            "objective_savings": "1",
        }
    )
    assert type(suggestion).model_validate_json(zero_post_work.model_dump_json()) == zero_post_work
    for invalid_work in (
        {"objective_before": "0", "objective_after": "0", "objective_savings": "0"},
        {"objective_before": "1", "objective_after": "-1", "objective_savings": "2"},
        {"objective_before": "1", "objective_after": "0", "objective_savings": "0"},
        {"objective_before": "1", "objective_after": "0", "objective_savings": "-1"},
        {"objective_before": "2", "objective_after": "0", "objective_savings": "1"},
    ):
        with pytest.raises(ValidationError):
            type(suggestion).model_validate({**suggestion.model_dump(), **invalid_work})


def test_report_and_suggestion_cross_field_truth_table() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationReport,
        OptimizationTarget,
        analyze,
    )
    from pydantic import ValidationError

    populated = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1) * (x + 1)",
        )
    )
    assert populated.status == "success" and populated.optimization is not None
    suggestion = populated.optimization.suggestions[0]
    assert OptimizationReport(requested_limit=3, status="complete").suggestions == ()
    assert OptimizationReport(
        requested_limit=3, status="complete", suggestions=(suggestion,)
    ).suggestions == (suggestion,)
    assert (
        OptimizationReport(
            requested_limit=3,
            status="incomplete",
            suggestions=(suggestion,),
            qualifications=("optimization candidate budget exhausted",),
        ).status
        == "incomplete"
    )
    for invalid in (
        {"requested_limit": 0, "status": "complete"},
        {"requested_limit": 3, "status": "disabled"},
        {"requested_limit": 3, "status": "incomplete"},
        {
            "requested_limit": 3,
            "status": "complete",
            "qualifications": ("unexpected qualification",),
        },
    ):
        with pytest.raises(ValidationError):
            OptimizationReport.model_validate(invalid)
    suggestion_data = suggestion.model_dump()
    transformation = suggestion.transformations[0]
    second_target = transformation.model_copy(
        update={"target": OptimizationTarget(kind="equation", name="other")}
    )
    for invalid in (
        {**suggestion_data, "transformations": ()},
        {**suggestion_data, "transformations": (transformation, transformation)},
        {**suggestion_data, "transformations": (transformation, second_target)},
        {**suggestion_data, "kind": "cross_equation_sharing"},
        {
            **suggestion_data,
            "target": transformation.target,
            "occurrences": transformation.occurrences,
            "original": transformation.original,
            "proposed": transformation.proposed,
        },
    ):
        with pytest.raises(ValidationError):
            type(suggestion).model_validate(invalid)
    schema = type(suggestion).model_json_schema()
    assert schema["properties"]["transformations"]["minItems"] == 1
    assert not ({"target", "occurrences", "original", "proposed"} & schema["properties"].keys())
    assert type(suggestion).model_validate_json(suggestion.model_dump_json()) == suggestion
    with pytest.raises(ValidationError):
        type(suggestion).model_validate({**suggestion_data, "savings": "-1"})
    with pytest.raises(ValidationError):
        type(suggestion).model_validate({**suggestion_data, "intermediate": None})
    with pytest.raises(ValidationError):
        type(suggestion).model_validate(
            {
                **suggestion_data,
                "conclusion": "proved_under_assumptions",
                "conditions": (),
                "assumptions_used": (),
            }
        )
    with pytest.raises(ValidationError):
        type(populated).model_validate({**populated.model_dump(), "optimization": None})


def test_public_proposals_reparse_and_reconstruct_independently() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    for expression in (
        "(x + 1) * (x + 1)",
        "1/x + 1/x",
        "x*y + x*z",
        "(x + 0) * y",
        "Sum(x*x + i, (i, 0, 3))",
    ):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
        assert outcome.status == "success" and outcome.optimization is not None
        plan = outcome.optimization.plans[0]
        proposed = _expression(plan.trace[0].transformations[0].proposed.normalized_sympy)
        assert plan.trace[0].candidate.expression is not None
        candidate = _expression(plan.trace[0].candidate.expression)
        # Transformations are target-local evidence; complete candidates carry
        # generated bindings and are intentionally a separate post-step state.
        if plan.trace[0].intermediate is not None:
            assert proposed != candidate
        else:
            assert proposed == candidate
        replayed = analyze(AnalysisRequest.model_validate(plan.trace[0].candidate.model_dump()))
        assert replayed.status == "success"


def test_unexpected_reasoning_and_verifier_defects_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import optimization as optimization_service

    def defect(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unexpected optimization defect")

    monkeypatch.setattr(optimization_service.ReasoningContext, "build", defect)
    result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    assert result.status == "success"
    assert result.optimization.status == "failed"

    monkeypatch.undo()
    from py_science.formula._optimization import search as search_owner

    monkeypatch.setattr(search_owner, "_verify_candidate", defect)
    result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    assert result.status == "success"
    assert result.optimization.status == "failed"


def test_complete_candidate_proof_reads_the_replayed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._optimization import replay as replay_owner
    from py_science.formula.computation import RetainedComputation
    from py_science.formula.optimization import _CandidateComputation

    original_complete_candidate = replay_owner._complete_candidate

    def falsified_complete_candidate(
        candidate: _CandidateComputation,
        request: AnalysisRequest,
        computed: RetainedComputation,
    ) -> AnalysisRequest:
        complete = original_complete_candidate(candidate, request, computed)
        return AnalysisRequest.model_validate(
            {**complete.model_dump(mode="python"), "expression": "0"}
        )

    monkeypatch.setattr(replay_owner, "_complete_candidate", falsified_complete_candidate)

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))

    assert outcome.status == "success"
    assert all(item.kind != "factoring" for item in outcome.optimization.suggestions)


def test_composed_search_v1_refuses_conflicting_final_qualifications() -> None:
    """Trace denominator obligations must share a model with request assumptions."""
    from py_science.formula import AnalysisRequest, Assumption, FormulaSyntax
    from py_science.formula.optimization import _qualifications_compatible

    conflicting = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x",
        assumptions=(Assumption(name="zero", relationship="x == 0"),),
    )
    compatible = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x",
        assumptions=(Assumption(name="nonzero", relationship="x > 0"),),
    )
    assert not _qualifications_compatible(("x != 0",), conflicting)
    assert _qualifications_compatible(("x != 0",), compatible)


def test_private_blockers_are_bounded_deduplicated_and_candidate_free() -> None:
    from py_science.formula._optimization.diagnostics import _OutcomeAccounting

    accounting = _OutcomeAccounting()
    accounting.missing_primitive_cost("repeated_call", "expression")
    accounting.missing_primitive_cost("repeated_call", "expression")
    for target in map(lambda value: f"target_{value}", range(32)):
        accounting.missing_primitive_cost("repeated_call", target)
    accounting.unproved_domain_or_cardinality("horner", "expression")
    accounting.evaluator_limit("horner", "expression")

    assert len(accounting.blockers) == 16
    assert accounting.blockers == tuple(
        sorted(
            accounting.blockers,
            key=lambda item: (item.reason, item.required_information, item.family, item.target),
        )
    )
    for blocker in accounting.blockers:
        assert blocker.reason in {
            "missing_primitive_cost",
            "unproved_domain_or_cardinality",
            "evaluator_limit",
        }
        assert blocker.required_information in {
            "declare_primitive_cost",
            "declare_domain_or_cardinality",
            "reduce_evaluator_complexity",
        }
        assert not hasattr(blocker, "candidate")
        assert not hasattr(blocker, "rejection")
        assert "f(x)" not in repr(blocker)
        assert "raw rejection" not in repr(blocker)
