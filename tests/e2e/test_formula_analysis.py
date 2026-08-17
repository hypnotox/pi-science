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
    EquationReport,
    FormulaSyntax,
    Interpretation,
    OperationCounts,
    SourceLocation,
    SymbolicOperationCounts,
    SystemReport,
    analyze,
)
from pydantic import ValidationError


def describe_outcome(outcome: AnalysisOutcome) -> str:
    if outcome.status == "success":
        return outcome.interpretation.normalized_sympy
    if outcome.status == "failure":
        return outcome.error.code.value
    assert_never(outcome)


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
    )


def test_analyze_counts_submitted_subtraction() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x - y")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x - y", normalized_latex="x - y"),
        operation_counts=OperationCounts(subtractions=1),
        abstract_work=1,
    )


def test_analyze_counts_submitted_multiplication() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * y")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x*y", normalized_latex="x y"),
        operation_counts=OperationCounts(multiplications=1),
        abstract_work=1,
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
    )


def test_analyze_counts_submitted_power() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x**2")

    outcome = analyze(request)

    assert outcome == AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x**2", normalized_latex="x^{2}"),
        operation_counts=OperationCounts(powers=1),
        abstract_work=1,
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


def test_malformed_syntax_returns_a_structured_failure() -> None:
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x +")

    outcome = analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.MALFORMED_SYNTAX
    assert outcome.error.message
    assert outcome.error.location is not None
    assert outcome.error.location.line == 1


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
        "-x",
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
