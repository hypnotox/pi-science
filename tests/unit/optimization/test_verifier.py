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
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    outcome = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * y + x * z")
    )
    assert outcome.status == "success"
    suggestions = tuple(plan.suggestion for plan in outcome.plans)
    suggestion = suggestions[0]
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


def test_result_search_scope_claim_and_suggestion_cross_field_truth_table() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationResult,
        OptimizationTarget,
        SearchScope,
        StrictImprovementClaim,
    )
    from pydantic import ValidationError

    populated = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1) * (x + 1)")
    )
    assert populated.status == "success"
    assert populated.classification == "plans_returned"
    assert populated.selection.projection_limit == populated.projection_limit
    assert populated.search_scope.completion == "complete"
    assert populated.projection_status == "complete"
    suggestions = tuple(plan.suggestion for plan in populated.plans)
    suggestion = suggestions[0]
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
    for invalid in (
        {**suggestion_data, "savings": "-1"},
        {**suggestion_data, "intermediate": None},
        {
            **suggestion_data,
            "conclusion": "proved_under_assumptions",
            "conditions": (),
            "assumptions_used": (),
        },
    ):
        with pytest.raises(ValidationError):
            type(suggestion).model_validate(invalid)
    result_data = populated.model_dump()
    for invalid in (
        {**result_data, "projection_limit": 0},
        {**result_data, "classification": "no_verified_improvement"},
        {**result_data, "projection_status": "truncated", "projection_qualifications": ()},
        {**result_data, "optimization": None},
    ):
        with pytest.raises(ValidationError):
            OptimizationResult.model_validate(invalid)
    with pytest.raises(ValidationError):
        SearchScope.model_validate(
            {**populated.search_scope.model_dump(), "completion": "incomplete"}
        )
    with pytest.raises(ValidationError):
        StrictImprovementClaim.model_validate(
            {**populated.plans[0].claim.model_dump(), "families": ()}
        )
    drifted_claim = populated.plans[0].claim.model_copy(update={"families": ("factoring",)})
    drifted_plan = populated.plans[0].model_copy(update={"claim": drifted_claim})
    with pytest.raises(ValidationError):
        OptimizationResult.model_validate({**result_data, "plans": (drifted_plan,)})
    drifted_limits = populated.plans[0].claim.limits.model_copy(
        update={"final_states": populated.plans[0].claim.limits.final_states + 1}
    )
    drifted_claim = populated.plans[0].claim.model_copy(update={"limits": drifted_limits})
    drifted_plan = populated.plans[0].model_copy(update={"claim": drifted_claim})
    with pytest.raises(ValidationError):
        OptimizationResult.model_validate({**result_data, "plans": (drifted_plan,)})


def test_public_proposals_reparse_and_reconstruct_independently() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    for expression in (
        "(x + 1) * (x + 1)",
        "1/x + 1/x",
        "x*y + x*z",
        "(x + 0) * y",
        "Sum(x*x + i, (i, 0, 3))",
    ):
        outcome = optimize_analysis(
            AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)
        )
        assert outcome.status == "success"
        plan = outcome.plans[0]
        proposed = _expression(plan.trace[0].transformations[0].proposed.normalized_sympy)
        assert plan.trace[0].candidate.expression is not None
        candidate = _expression(plan.trace[0].candidate.expression)
        # Transformations are target-local evidence; complete candidates carry
        # generated bindings and are intentionally a separate post-step state.
        if plan.trace[0].intermediate is not None:
            assert proposed != candidate
        else:
            assert proposed == candidate
        replayed = optimize_analysis(
            AnalysisRequest.model_validate(plan.trace[0].candidate.model_dump())
        )
        assert replayed.status == "success"


def test_unexpected_reasoning_and_verifier_defects_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from goal_requests import goal_request
    from py_science.formula import AnalysisRequest, FormulaSyntax, optimize
    from py_science.formula._optimization import search as search_owner

    def defect(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unexpected optimization defect")

    request = goal_request(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    monkeypatch.setattr(search_owner.ReasoningContext, "build", defect)
    result = optimize(request)
    assert result.status == "failure"

    monkeypatch.undo()
    monkeypatch.setattr(search_owner, "_verify_candidate", defect)
    result = optimize(request)
    assert result.status == "failure"


def test_complete_candidate_proof_reads_the_replayed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax
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

    outcome = optimize_analysis(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))

    assert outcome.status == "success"
    assert all(
        item.kind != "factoring" for item in tuple(plan.suggestion for plan in outcome.plans)
    )


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
