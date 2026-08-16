from pathlib import Path
from typing import assert_never

import pytest
from pydantic import ValidationError

from pi_science import (
    EvaluationError,
    EvaluationErrorCode,
    EvaluationFailure,
    EvaluationOutcome,
    EvaluationRequest,
    EvaluationSuccess,
    FormulaSyntax,
    Interpretation,
    OperationCounts,
    SourceLocation,
    evaluate,
)


def describe_outcome(outcome: EvaluationOutcome) -> str:
    if outcome.status == "success":
        return outcome.interpretation.normalized_sympy
    if outcome.status == "failure":
        return outcome.error.code.value
    assert_never(outcome)


def test_structured_contract_is_strict_frozen_and_discriminated() -> None:
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(
            {"syntax": FormulaSyntax.SYMPY, "expression": "x", "unexpected": True}
        )

    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate({"syntax": "sympy", "expression": "x"})

    with pytest.raises(ValidationError):
        SourceLocation.model_validate({"line": "1", "column": 0})

    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x")
    with pytest.raises(ValidationError):
        request.__setattr__("expression", "y")

    success: EvaluationOutcome = EvaluationSuccess(
        interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
        operation_counts=OperationCounts(),
        abstract_work=0,
    )
    failure: EvaluationOutcome = EvaluationFailure(
        error=EvaluationError(
            code=EvaluationErrorCode.UNSUPPORTED_CONSTRUCT,
            message="unsupported",
            location=SourceLocation(line=1, column=0),
        )
    )

    assert describe_outcome(success) == "x"
    assert describe_outcome(failure) == "unsupported_construct"


def test_evaluate_returns_normalized_interpretation() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1")

    outcome = evaluate(request)

    assert outcome == EvaluationSuccess(
        interpretation=Interpretation(normalized_sympy="x + 1", normalized_latex="x + 1"),
        operation_counts=OperationCounts(additions=1),
        abstract_work=1,
    )


def test_evaluate_counts_submitted_subtraction() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x - y")

    outcome = evaluate(request)

    assert outcome == EvaluationSuccess(
        interpretation=Interpretation(normalized_sympy="x - y", normalized_latex="x - y"),
        operation_counts=OperationCounts(subtractions=1),
        abstract_work=1,
    )


def test_evaluate_counts_submitted_multiplication() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x * y")

    outcome = evaluate(request)

    assert outcome == EvaluationSuccess(
        interpretation=Interpretation(normalized_sympy="x*y", normalized_latex="x y"),
        operation_counts=OperationCounts(multiplications=1),
        abstract_work=1,
    )


def test_evaluate_counts_submitted_division() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x / y")

    outcome = evaluate(request)

    assert outcome == EvaluationSuccess(
        interpretation=Interpretation(
            normalized_sympy="x/y",
            normalized_latex=r"\frac{x}{y}",
        ),
        operation_counts=OperationCounts(divisions=1),
        abstract_work=1,
    )


def test_evaluate_counts_submitted_power() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x**2")

    outcome = evaluate(request)

    assert outcome == EvaluationSuccess(
        interpretation=Interpretation(normalized_sympy="x**2", normalized_latex="x^{2}"),
        operation_counts=OperationCounts(powers=1),
        abstract_work=1,
    )


@pytest.mark.parametrize(
    ("expression", "normalized"),
    [("-1", "-1"), ("+1", "1"), ("- 1", "-1"), ("-(1)", "-1")],
)
def test_signed_integer_literals_have_no_operation_cost(
    expression: str,
    normalized: str,
) -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = evaluate(request)

    assert outcome == EvaluationSuccess(
        interpretation=Interpretation(
            normalized_sympy=normalized,
            normalized_latex=normalized,
        ),
        operation_counts=OperationCounts(),
        abstract_work=0,
    )


def test_nested_formula_counts_submitted_operators_before_normalization() -> None:
    request = EvaluationRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="a - b / c + d * e**2",
    )

    outcome = evaluate(request)

    assert isinstance(outcome, EvaluationSuccess)
    assert outcome.operation_counts == OperationCounts(
        additions=1,
        subtractions=1,
        multiplications=1,
        divisions=1,
        powers=1,
    )
    assert outcome.abstract_work == 5


def test_malformed_syntax_returns_a_structured_failure() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x +")

    outcome = evaluate(request)

    assert isinstance(outcome, EvaluationFailure)
    assert outcome.error.code is EvaluationErrorCode.MALFORMED_SYNTAX
    assert outcome.error.message
    assert outcome.error.location is not None
    assert outcome.error.location.line == 1


@pytest.mark.parametrize(
    "expression",
    [
        "f(x)",
        "x.real",
        "x[0]",
        "[x]",
        "[x for x in y]",
        "1.5",
        "True",
        "x and y",
        "x < y",
        "-x",
        "--1",
        "x // y",
    ],
)
def test_out_of_grammar_constructs_return_structured_failures(expression: str) -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = evaluate(request)

    assert isinstance(outcome, EvaluationFailure)
    assert outcome.error.code is EvaluationErrorCode.UNSUPPORTED_CONSTRUCT
    assert outcome.error.message
    assert outcome.error.location is not None
    assert outcome.error.location.line == 1


def test_submitted_python_is_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    expression = f"__import__('pathlib').Path({str(marker)!r}).write_text('unsafe')"
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = evaluate(request)

    assert isinstance(outcome, EvaluationFailure)
    assert outcome.error.code is EvaluationErrorCode.UNSUPPORTED_CONSTRUCT
    assert not marker.exists()


def test_excessively_deep_formulas_return_structured_failures() -> None:
    expression = "+".join("x" for _ in range(1_000))
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression=expression)

    outcome = evaluate(request)

    assert isinstance(outcome, EvaluationFailure)
    assert outcome.error.code is EvaluationErrorCode.EXPRESSION_TOO_COMPLEX


def test_identical_requests_produce_identical_results() -> None:
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="(x - y) / z**2")

    assert evaluate(request) == evaluate(request)
