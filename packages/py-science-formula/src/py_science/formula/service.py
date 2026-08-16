from py_science.formula.analyzer import OperationTally, count_operations
from py_science.formula.models import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisRequest,
    AnalysisSuccess,
    Interpretation,
    OperationCounts,
    SourceLocation,
)
from py_science.formula.parser import ParseFailure, ParseFailureKind, parse_expression
from py_science.formula.sympy_backend import NormalizationError, render


def analyze(request: AnalysisRequest) -> AnalysisOutcome:
    parsed = parse_expression(request.expression)
    if isinstance(parsed, ParseFailure):
        return AnalysisFailure(
            error=AnalysisError(
                code=_error_code(parsed.kind),
                message=parsed.message,
                location=_location(parsed),
            )
        )

    try:
        normalized = render(parsed)
    except NormalizationError:
        return AnalysisFailure(
            error=AnalysisError(
                code=AnalysisErrorCode.NORMALIZATION_FAILED,
                message="the validated expression could not be normalized",
            )
        )

    tally = count_operations(parsed)
    return AnalysisSuccess(
        interpretation=Interpretation(
            normalized_sympy=normalized.sympy,
            normalized_latex=normalized.latex,
        ),
        operation_counts=_operation_counts(tally),
        abstract_work=tally.total,
    )


def _error_code(kind: ParseFailureKind) -> AnalysisErrorCode:
    match kind:
        case ParseFailureKind.MALFORMED:
            return AnalysisErrorCode.MALFORMED_SYNTAX
        case ParseFailureKind.UNSUPPORTED:
            return AnalysisErrorCode.UNSUPPORTED_CONSTRUCT
        case ParseFailureKind.TOO_COMPLEX:
            return AnalysisErrorCode.EXPRESSION_TOO_COMPLEX


def _location(failure: ParseFailure) -> SourceLocation | None:
    if (
        failure.line is None
        or failure.line < 1
        or failure.column is None
        or failure.column < 0
    ):
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
