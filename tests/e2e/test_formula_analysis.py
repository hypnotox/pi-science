# ruff: noqa: E501
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false
from pathlib import Path
from typing import assert_never

import pytest
from py_science.formula import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisRequest,
    AnalysisSuccess,
    Assumption,
    ClosedFormEvidence,
    ClosedFormQuery,
    EquationReport,
    EquivalenceQuery,
    FormulaSyntax,
    Interpretation,
    MathematicalDomain,
    OperationCounts,
    OptimizationConfig,
    OptimizationReport,
    SourceLocation,
    SymbolicOperationCounts,
    SystemReport,
    VariableDeclaration,
    analyze,
)
from pydantic import ValidationError


def describe_outcome(outcome: AnalysisOutcome) -> str:
    if outcome.status == "success":
        return outcome.interpretation.normalized_sympy
    if outcome.status == "failure":
        return outcome.error.code.value
    assert_never(outcome)


def test_exact_algorithmic_sum_v1_e2e_replays_without_changing_submitted_work() -> None:
    source = "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, 100))"
    baseline = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=source)
    )
    enabled = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=source,
            optimization=OptimizationConfig(
                max_suggestions=16,
                enabled_algorithmic_families=("finite_polynomial_sum_v1",),
            ),
        )
    )
    assert isinstance(baseline, AnalysisSuccess) and isinstance(enabled, AnalysisSuccess)
    assert enabled.abstract_work == baseline.abstract_work
    plan = next(
        plan
        for plan in enabled.optimization.plans
        if any(step.kind == "finite_polynomial_sum_v1" for step in plan.trace)
    )
    replay = analyze(AnalysisRequest.model_validate(plan.candidate.model_dump()))
    assert isinstance(replay, AnalysisSuccess)
    assert replay.interpretation.normalized_sympy == "21591278"
    assert plan.suggestion.finite_precision_qualification == "exact_symbolic_only"


def test_general_query_results_do_not_change_submitted_expression_work() -> None:
    baseline = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1"))
    queried = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + 1",
            queries=(
                EquivalenceQuery(name="same", comparison="1 + x"),
                ClosedFormQuery(name="later"),
            ),
        )
    )
    assert isinstance(baseline, AnalysisSuccess)
    assert isinstance(queried, AnalysisSuccess)
    assert queried.operation_counts == baseline.operation_counts
    assert queried.abstract_work == baseline.abstract_work
    assert queried.direct_work_applicability == baseline.direct_work_applicability
    assert queried.queries[0].answers[0].conclusion == "proved"
    assert queried.queries[1].answers[0].conclusion == "unresolved"


def test_asymptotic_query_is_expression_semantics_not_scenario_work_growth() -> None:
    baseline = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="1/(x - 1)"))
    queried = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="1/(x - 1)",
        queries=({"name": "local", "kind": "asymptotic", "variable": "x", "point": "1", "direction": "left", "order": 2},),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(queried, AnalysisSuccess)
    assert queried.operation_counts == baseline.operation_counts
    assert queried.abstract_work == baseline.abstract_work
    answer = queried.queries[0].answers[0]
    assert answer.evidence is not None and answer.evidence.kind == "asymptotic"
    assert answer.conditions == ("x -> 1 (left)", "x - 1 != 0")


def test_property_and_directional_limit_queries_preserve_submitted_work() -> None:
    baseline = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="1/(x - 1)"))
    queried = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="1/(x - 1)",
        variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        queries=(
            {"name": "properties", "kind": "properties", "checks": ({"kind": "valid_domain", "variable": "x"}, {"kind": "singularities", "variable": "x"}, {"kind": "sign"})},
            {"name": "limit", "kind": "limit", "variable": "x", "point": "1", "direction": "both"},
        ),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(queried, AnalysisSuccess)
    assert queried.operation_counts == baseline.operation_counts
    assert queried.abstract_work == baseline.abstract_work
    assert queried.queries[0].answers[0].conclusion == "proved"
    limit = queried.queries[1].answers[0].evidence
    assert limit is not None and limit.kind == "limit" and limit.exists is False


def test_closed_form_query_preserves_submitted_nonfinite_work() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k * 2**k, (k, 0, 3))",
        queries=(ClosedFormQuery(name="series"),),
    ))
    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.queries[0].answers[0].conclusion == "proved_under_assumptions"
    assert outcome.queries[0].answers[0].derived_candidates


def test_expression_derived_target_feeds_equivalence_and_limit_without_changing_work() -> None:
    baseline = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k * 2**k, (k, 0, 3))",
    ))
    queried = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k * 2**k, (k, 0, 3))",
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {
                "name": "same",
                "kind": "equivalence",
                "target": {"kind": "derived", "query": "closed"},
                "comparison": "34",
            },
            {
                "name": "constant_limit",
                "kind": "limit",
                "target": {"kind": "derived", "query": "closed"},
                "variable": "x",
                "point": "oo",
            },
        ),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(queried, AnalysisSuccess)
    assert queried.operation_counts == baseline.operation_counts
    assert queried.abstract_work == baseline.abstract_work
    assert queried.queries[1].normalized_target is not None
    assert queried.queries[1].normalized_target.normalized_sympy == "34"
    assert queried.queries[1].answers[0].conclusion == "proved_under_assumptions"
    assert queried.queries[2].answers[0].conclusion == "proved_under_assumptions"


def test_nested_closed_form_and_explicit_reuse_preserve_expression_work() -> None:
    expression = "Sum(Sum(1, (l, -k, k)), (k, 0, p))"
    variables = {"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}
    baseline = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression=expression, variables=variables
    ))
    queried = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=expression,
        variables=variables,
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {"name": "same", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "(p + 1)**2"},
            {"name": "growth", "kind": "limit", "target": {"kind": "derived", "query": "closed"}, "variable": "p", "point": "oo"},
        ),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(queried, AnalysisSuccess)
    assert queried.operation_counts == baseline.operation_counts
    assert queried.abstract_work == baseline.abstract_work
    closed = queried.queries[0].answers[0]
    assert closed.conclusion == "proved"
    assert isinstance(closed.evidence, ClosedFormEvidence)
    assert closed.evidence.verification == "finite_antidifference"
    assert queried.queries[1].answers[0].conclusion == "proved"
    assert queried.queries[2].answers[0].conclusion == "proved"


def test_closed_form_e2e_uses_global_bounds_without_changing_nonfinite_work() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k*q**k, (k, 0, n))",
        variables={"n": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)},
        assumptions=(Assumption(name="q_below_one", relationship="q < 1"),),
        queries=(ClosedFormQuery(name="bounded"),),
    ))
    assert isinstance(outcome, AnalysisSuccess)
    answer = outcome.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert {use.name for use in answer.assumptions_used} == {"q_below_one"}
    assert isinstance(answer.evidence, ClosedFormEvidence)
    assert answer.evidence.verification == "finite_antidifference"
    # The original finite iterator remains the submitted-work source, not the candidate.
    assert outcome.abstract_work is not None


def test_structured_contract_is_strict_frozen_and_discriminated() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            {"syntax": FormulaSyntax.SYMPY, "expression": "x", "unexpected": True}
        )

    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate({"syntax": "sympy", "expression": "x"})

    with pytest.raises(ValidationError):
        SourceLocation.model_validate({"line": "1", "column": 0})

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x")
    with pytest.raises(ValidationError):
        request.__setattr__("expression", "y")

    success: AnalysisOutcome = AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
        operation_counts=OperationCounts(),
        abstract_work=0,
    )
    failure: AnalysisOutcome = AnalysisFailure(
        error=AnalysisError(
            code=AnalysisErrorCode.UNSUPPORTED_CONSTRUCT,
            message="unsupported",
            location=SourceLocation(line=1, column=0),
        )
    )

    assert describe_outcome(success) == "x"
    assert describe_outcome(failure) == "unsupported_construct"


def test_direct_work_models_reject_contradictory_variants() -> None:
    interpretation = Interpretation(normalized_sympy="x", normalized_latex="x")
    counts = OperationCounts()
    symbolic = SymbolicOperationCounts()
    with pytest.raises(ValidationError):
        AnalysisSuccess(
            interpretation=interpretation,
            operation_counts=counts,
            abstract_work=None,
            direct_work_applicability="finite",
        )
    with pytest.raises(ValidationError):
        EquationReport(
            name="expression",
            interpretation=interpretation,
            operation_counts=counts,
            aggregate_operation_counts=symbolic,
            aggregate_work="0",
            direct_work_applicability="not_finite",
            direct_work_blockers=("blocked",),
            primitive_invocations={},
        )
    with pytest.raises(ValidationError):
        SystemReport(
            equations=(),
            aggregate_operation_counts=None,
            total_work=None,
            direct_work_applicability="not_finite",
            direct_work_blockers=(),
            primitive_invocations=None,
        )
    nonfinite_equation = EquationReport(
        name="expression",
        interpretation=interpretation,
        operation_counts=counts,
        aggregate_operation_counts=None,
        aggregate_work=None,
        direct_work_applicability="not_finite",
        direct_work_blockers=("blocked",),
        primitive_invocations=None,
    )
    with pytest.raises(ValidationError):
        SystemReport(
            equations=(nonfinite_equation,),
            aggregate_operation_counts=symbolic,
            total_work="0",
            primitive_invocations={},
        )
    nonfinite_system = SystemReport(
        equations=(nonfinite_equation,),
        aggregate_operation_counts=None,
        total_work=None,
        direct_work_applicability="not_finite",
        direct_work_blockers=("equation expression: blocked",),
        primitive_invocations=None,
    )
    with pytest.raises(ValidationError):
        AnalysisSuccess(
            interpretation=interpretation,
            operation_counts=counts,
            abstract_work=0,
            system=nonfinite_system,
        )


def test_analyze_returns_normalized_interpretation() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x + 1", normalized_latex="x + 1"),
        operation_counts=OperationCounts(additions=1),
        abstract_work=1,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


def test_analyze_counts_submitted_subtraction() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x - y")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x - y", normalized_latex="x - y"),
        operation_counts=OperationCounts(subtractions=1),
        abstract_work=1,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


def test_analyze_counts_submitted_multiplication() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * y")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x*y", normalized_latex="x y"),
        operation_counts=OperationCounts(multiplications=1),
        abstract_work=1,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


def test_analyze_counts_submitted_division() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x / y")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(
            normalized_sympy="x/y",
            normalized_latex=r"\frac{x}{y}",
        ),
        operation_counts=OperationCounts(divisions=1),
        abstract_work=1,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


def test_analyze_counts_submitted_power() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x**2")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x**2", normalized_latex="x^{2}"),
        operation_counts=OperationCounts(powers=1),
        abstract_work=1,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


def test_numeric_powers_are_normalized_without_eager_exponentiation() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="2**100000")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(
            normalized_sympy="2**100000",
            normalized_latex="2^{100000}",
        ),
        operation_counts=OperationCounts(powers=1),
        abstract_work=1,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


@pytest.mark.parametrize(
    "expression",
    [
        "2**100000 + x",
        "2**100000 - x",
        "2**100000 * x",
        "2**100000 / x",
        "(2**100000)**x",
    ],
)
def test_compound_numeric_powers_remain_unnormalized(expression: str) -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisSuccess)
    assert "2**100000" in outcome.interpretation.normalized_sympy


@pytest.mark.parametrize(
    ("expression", "normalized"),
    [("-1", "-1"), ("+1", "1"), ("- 1", "-1"), ("-(1)", "-1")],
)
def test_signed_integer_literals_have_no_operation_cost(
    expression: str,
    normalized: str,
) -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(
            normalized_sympy=normalized,
            normalized_latex=normalized,
        ),
        operation_counts=OperationCounts(),
        abstract_work=0,
        optimization=OptimizationReport(requested_limit=3, status="complete"),
    )


def test_nested_formula_counts_submitted_operators_before_normalization() -> None:
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="a - b / c + d * e**2",
    )

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.operation_counts == OperationCounts(
        additions=1,
        subtractions=1,
        multiplications=1,
        divisions=1,
        powers=1,
    )
    assert outcome.abstract_work == 5


def test_malformed_syntax_without_precise_offset_returns_null_location() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x +")

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.MALFORMED_SYNTAX
    assert outcome.error.message
    assert outcome.error.location is None
    assert outcome.error.source is not None
    assert outcome.error.source.span is None


def test_empty_expression_returns_malformed_syntax_without_an_invalid_location() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="")

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.MALFORMED_SYNTAX
    assert outcome.error.location is None


def test_non_utf8_expression_returns_consumer_facing_malformed_syntax() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="\ud800")

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.MALFORMED_SYNTAX
    assert outcome.error.message == "expression is not valid UTF-8"
    assert outcome.error.location is None


@pytest.mark.parametrize(
    "expression",
    [
        "x.real",
        "[x]",
        "[x for x in y]",
        "True",
        "x and y",
        "x < y",
        "--1",
        "x // y",
    ],
)
def test_out_of_grammar_constructs_return_structured_failures(expression: str) -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.UNSUPPORTED_CONSTRUCT
    assert outcome.error.message
    if expression != "x < y":
        assert outcome.error.location is not None
        assert outcome.error.location.line == 1


def test_submitted_python_is_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    expression = f"__import__('pathlib').Path({str(marker)!r}).write_text('unsafe')"
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.UNSUPPORTED_CONSTRUCT
    assert not marker.exists()


def test_oversized_input_reports_the_public_byte_limit() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x" * 65_537)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX
    assert outcome.error.message == (
        "expression exceeds the maximum input size of 65536 UTF-8 bytes"
    )


def test_excessive_nesting_reports_the_public_depth_limit() -> None:
    expression = "+".join("x" for _ in range(130))
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX
    assert outcome.error.message == "expression nesting exceeds the maximum depth of 128"


def _balanced_sum(terms: list[str]) -> str:
    while len(terms) > 1:
        paired = [
            f"({terms[index]}+{terms[index + 1]})"
            for index in range(0, len(terms) - 1, 2)
        ]
        if len(terms) % 2:
            paired.append(terms[-1])
        terms = paired
    return terms[0]


def test_internal_node_budget_uses_a_generic_consumer_message() -> None:
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=_balanced_sum(["x"] * 2_049),
    )

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX
    assert outcome.error.message == "expression is too complex"


def test_signed_literals_count_as_one_internal_node() -> None:
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=_balanced_sum(["-1"] * 2_048),
    )

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisSuccess)


def test_signed_literals_still_respect_the_internal_node_budget() -> None:
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=_balanced_sum(["-1"] * 2_049),
    )

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX
    assert outcome.error.message == "expression is too complex"


def test_oversized_integer_reports_the_public_literal_limit() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="9" * 1_025)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX
    assert outcome.error.message == (
        "integer literal exceeds the maximum size of approximately 1024 decimal digits"
    )


@pytest.mark.parametrize(
    "expression",
    ["9" * 5_000, "0" * 1_025, "_".join("0" for _ in range(1_025))],
)
def test_oversized_decimal_tokens_report_the_public_literal_limit(
    expression: str,
) -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX
    assert outcome.error.message == (
        "integer literal exceeds the maximum size of approximately 1024 decimal digits"
    )


def test_excessively_deep_formulas_return_structured_failures() -> None:
    expression = "+".join("x" for _ in range(1_000))
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.EXPRESSION_TOO_COMPLEX


def test_identical_requests_produce_identical_results() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x - y) / z**2")

    assert analyze(request) == analyze(request)


def test_decimal_literals_are_rendered_as_canonical_exact_rationals() -> None:
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="1.50 + x"))
    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.interpretation.normalized_sympy == "x + 3/2"
    assert outcome.direct_work_applicability == "finite"
    assert outcome.direct_work_blockers == ()


def test_complete_candidate_replays_factoring_neutral_and_horner_with_context() -> None:
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import (
        _complete_candidate,
        _generate_candidates,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="a*x**3 + a*x**2 + 0",
        variables={
            "a": VariableDeclaration(domain=MathematicalDomain.REAL),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        assumptions=(),
        definitions=(),
        optimization=OptimizationConfig(max_suggestions=16),
    )
    retained = analyze_retained(request)
    assert isinstance(retained, object) and not isinstance(retained, AnalysisFailure)
    candidates, _ = _generate_candidates(retained, _OptimizationBudget())
    kinds = {"factoring", "redundant_operation_removal", "horner"}
    for candidate in candidates:
        if candidate.kind not in kinds:
            continue
        replayed = analyze_retained(_complete_candidate(candidate, request, retained))
        assert not isinstance(replayed, AnalysisFailure)
        assert replayed.expression is not None
        assert replayed.knowledge == retained.knowledge


def test_dense_polynomial_horner_advice_is_independently_proved_and_lower_work() -> None:
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="a*x**3 + b*x**2 + c*x + d",
        optimization=OptimizationConfig(max_suggestions=16),
    )
    enabled = analyze(request)
    disabled = analyze(
        request.model_copy(update={"optimization": OptimizationConfig(max_suggestions=0)})
    )

    assert isinstance(enabled, AnalysisSuccess)
    assert isinstance(disabled, AnalysisSuccess)
    assert enabled.model_copy(update={"optimization": None}) == disabled.model_copy(
        update={"optimization": None}
    )
    suggestion = next(item for item in enabled.optimization.suggestions if item.kind == "horner")
    assert suggestion.conclusion == "proved"
    assert int(suggestion.work_before) > int(suggestion.work_after) > 0
    assert int(suggestion.savings) == int(suggestion.work_before) - int(suggestion.work_after)
    assert suggestion.finite_precision_qualification == "exact_symbolic_only"


def test_objective_v1_custom_selection_preserves_ordinary_analysis_fields() -> None:
    base = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1)*(x + 1) + (y*z + y*w)",
    )
    default = analyze(base)
    weighted = analyze(
        AnalysisRequest.model_validate(
            {
                **base.model_dump(),
                "optimization": {
                    "objective": {
                        "kind": "weighted_operations_v1",
                        "weights": {
                            "additions": "1", "subtractions": "1",
                            "multiplications": "1", "divisions": "1", "powers": "5/2",
                        },
                    }
                },
            }
        )
    )
    assert isinstance(default, AnalysisSuccess) and isinstance(weighted, AnalysisSuccess)
    assert default.model_copy(update={"optimization": None}) == weighted.model_copy(
        update={"optimization": None}
    )
    assert default.optimization.plans[0].objective.kind == "unit_work_v1"
    assert weighted.optimization.plans[0].objective.kind == "weighted_operations_v1"
