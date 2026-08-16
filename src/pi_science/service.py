from pi_science.analyzer import OperationTally, count_operations
from pi_science.models import (
    EvaluationError,
    EvaluationErrorCode,
    EvaluationFailure,
    EvaluationOutcome,
    EvaluationRequest,
    EvaluationSuccess,
    Interpretation,
    OperationCounts,
    SourceLocation,
)
from pi_science.parser import ParseFailure, ParseFailureKind, parse_expression
from pi_science.sympy_backend import render


def evaluate(request: EvaluationRequest) -> EvaluationOutcome:
    parsed = parse_expression(request.expression)
    if isinstance(parsed, ParseFailure):
        return EvaluationFailure(
            error=EvaluationError(
                code=_error_code(parsed.kind),
                message=parsed.message,
                location=_location(parsed),
            )
        )

    try:
        normalized = render(parsed)
    except Exception:
        return EvaluationFailure(
            error=EvaluationError(
                code=EvaluationErrorCode.NORMALIZATION_FAILED,
                message="the validated expression could not be normalized",
            )
        )

    tally = count_operations(parsed)
    return EvaluationSuccess(
        interpretation=Interpretation(
            normalized_sympy=normalized.sympy,
            normalized_latex=normalized.latex,
        ),
        operation_counts=_operation_counts(tally),
        abstract_work=tally.total,
    )


def _error_code(kind: ParseFailureKind) -> EvaluationErrorCode:
    match kind:
        case ParseFailureKind.MALFORMED:
            return EvaluationErrorCode.MALFORMED_SYNTAX
        case ParseFailureKind.UNSUPPORTED:
            return EvaluationErrorCode.UNSUPPORTED_CONSTRUCT
        case ParseFailureKind.TOO_COMPLEX:
            return EvaluationErrorCode.EXPRESSION_TOO_COMPLEX


def _location(failure: ParseFailure) -> SourceLocation | None:
    if failure.line is None or failure.column is None:
        return None
    return SourceLocation(line=failure.line, column=failure.column)


def _operation_counts(tally: OperationTally) -> OperationCounts:
    return OperationCounts(
        additions=tally.additions,
        subtractions=tally.subtractions,
        multiplications=tally.multiplications,
        divisions=tally.divisions,
        powers=tally.powers,
    )
