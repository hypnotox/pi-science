# ruff: noqa: E501
# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Bounded general-context query evaluation; it never contributes submitted work."""
from __future__ import annotations

from dataclasses import dataclass

from py_science.formula.asymptotics import asymptotic_answer
from py_science.formula.equivalence import equivalence_answer
from py_science.formula.expressions import (
    Equation,
    Expression,
    ExpressionTooComplex,
    Relationship,
    Sum,
    expression_children,
    lower_let_bindings,
)
from py_science.formula.models import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisFailure,
    AsymptoticResult,
    ClosedFormQuery,
    ClosedFormResult,
    EquivalenceQuery,
    EquivalenceResult,
    Interpretation,
    LimitQuery,
    LimitResult,
    PropertiesQuery,
    PropertiesResult,
    QueryAnswer,
    QueryRequest,
    QueryResult,
    ResolvedTarget,
    SourceLocation,
    SourceReference,
    SourceSpan,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.properties import afmm_tail_property_answer, limit_answer, property_answer
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.series import derive_closed_form

UNIMPLEMENTED = "query kind is not implemented in this release slice"


@dataclass(frozen=True, slots=True)
class QueryTarget:
    target: ResolvedTarget
    expression: Expression
    interpretation: Interpretation


def evaluate_queries(
    queries: tuple[QueryRequest, ...],
    target: QueryTarget,
    reasoning: ReasoningContext | None,
) -> tuple[QueryResult, ...] | AnalysisFailure:
    results: list[QueryResult] = []
    try:
        represented_expression = lower_let_bindings(target.expression)
    except ExpressionTooComplex:
        represented_expression = target.expression
    for position, query in enumerate(queries):
        if query.target is not None and query.target != target.target:
            return _failure("query target is unknown", f"queries[{position}].target")
        if isinstance(query, EquivalenceQuery):
            answer = _equivalence(query, represented_expression, reasoning, position)
            if isinstance(answer, AnalysisFailure):
                return answer
            result: QueryResult = EquivalenceResult(
                name=query.name,
                target=target.target,
                normalized_target=target.interpretation,
                summary="equivalence comparison",
                answers=(answer,),
            )
        elif isinstance(query, PropertiesQuery):
            expression, qualification = _property_expression(represented_expression, reasoning)
            answers = tuple(
                afmm_tail_property_answer(represented_expression, item, reasoning)
                or property_answer(expression, item, reasoning)
                for item in query.checks
            )
            answers = tuple(_with_closed_form_qualification(answer, qualification) for answer in answers)
            result = PropertiesResult(
                name=query.name,
                target=target.target,
                normalized_target=target.interpretation,
                summary="bounded exact univariate properties",
                answers=answers,
            )
        elif isinstance(query, ClosedFormQuery):
            answer = derive_closed_form(represented_expression, reasoning)
            result = ClosedFormResult(name=query.name, target=target.target, normalized_target=target.interpretation, summary="qualified bounded series closed form", answers=(answer,))
        elif isinstance(query, LimitQuery):
            expression, qualification = _property_expression(represented_expression, reasoning)
            answer = _with_closed_form_qualification(limit_answer(expression, query, reasoning), qualification)
            result = LimitResult(name=query.name, target=target.target, normalized_target=target.interpretation, summary="bounded exact directional limit", answers=(answer,))
        else:
            expression, qualification = _property_expression(represented_expression, reasoning)
            answer = _with_closed_form_qualification(
                asymptotic_answer(
                    expression,
                    query,
                    reasoning,
                    original_expression=represented_expression,
                ),
                qualification,
            )
            result = AsymptoticResult(name=query.name, target=target.target, normalized_target=target.interpretation, summary="qualified bounded asymptotic expansion", answers=(answer,))
        results.append(result)
    return tuple(results)


def _property_expression(
    expression: Expression, reasoning: ReasoningContext | None
) -> tuple[Expression, QueryAnswer | None]:
    """Replace only a Task-3-proved series before the Task-4 rational rules."""
    if not any(isinstance(item, Sum) for item in _walk(expression)):
        return expression, None
    # Nested polynomial derivation is intentionally direct-closed-form only.
    if any(isinstance(item, Sum) and any(isinstance(child, Sum) for child in _walk(item.body)) for item in _walk(expression)):
        return expression, QueryAnswer(conclusion="unresolved", blockers=("nested polynomial closed forms require an explicit closed_form query",))
    closed = derive_closed_form(expression, reasoning)
    if closed.conclusion not in {"proved", "proved_under_assumptions"} or not closed.derived_candidates:
        return expression, closed
    source = closed.derived_candidates[0].interpretation.normalized_sympy
    parsed = parse_expression(source)
    if isinstance(parsed, (ParseFailure, tuple)):
        return expression, QueryAnswer(conclusion="unresolved", blockers=("closed-form candidate cannot be parsed",))
    if isinstance(parsed, (Equation, Relationship)):
        return expression, QueryAnswer(conclusion="unresolved", blockers=("closed-form candidate cannot be parsed",))
    return parsed, closed


def _with_closed_form_qualification(answer: QueryAnswer, closed: QueryAnswer | None) -> QueryAnswer:
    if closed is None or answer.conclusion not in {"proved", "proved_under_assumptions"}:
        return answer
    if closed.blockers == ("closed-form candidate cannot be parsed",):
        # The AFMM-tail property rule works from the submitted bounded sum rather
        # than its symbolic-power rendering, so this parsing representation limit
        # cannot invalidate its independently qualified conclusion.
        return answer
    if closed.conclusion not in {"proved", "proved_under_assumptions"}:
        return QueryAnswer(
            check=answer.check,
            conclusion="unresolved",
            blockers=closed.blockers or ("closed-form replacement is unresolved",),
            relevant_unsupported_assumptions=closed.relevant_unsupported_assumptions,
        )
    return answer.model_copy(update={
        "conclusion": "proved_under_assumptions" if closed.conditions or closed.assumptions_used else answer.conclusion,
        "conditions": tuple(dict.fromkeys((*answer.conditions, *closed.conditions))),
        "assumptions_used": _unique_uses((*answer.assumptions_used, *closed.assumptions_used)),
        "relevant_unsupported_assumptions": tuple(dict.fromkeys((*answer.relevant_unsupported_assumptions, *closed.relevant_unsupported_assumptions))),
    })


def _walk(value: Expression):  # pyright: ignore[reportUnknownParameterType]
    yield value
    for child in expression_children(value):
        yield from _walk(child)


def _failure(
    message: str,
    path: str,
    excerpt: str | None = None,
    parsed_failure: ParseFailure | None = None,
) -> AnalysisFailure:
    location = None
    span = None
    if (
        parsed_failure is not None
        and parsed_failure.line is not None
        and parsed_failure.column is not None
    ):
        location = SourceLocation(line=parsed_failure.line, column=parsed_failure.column)
        if parsed_failure.end_line is not None and parsed_failure.end_column is not None:
            span = SourceSpan(
                start=location,
                end=SourceLocation(
                    line=parsed_failure.end_line,
                    column=parsed_failure.end_column,
                ),
            )
    return AnalysisFailure(
        error=AnalysisError(
            code=AnalysisErrorCode.MALFORMED_SYNTAX,
            message=message,
            location=location,
            source=SourceReference(
                path=path,
                span=span,
                excerpt=excerpt[:160] if excerpt is not None else None,
            ),
        )
    )


def _equivalence(
    query: EquivalenceQuery,
    expression: Expression,
    reasoning: ReasoningContext | None,
    position: int,
) -> QueryAnswer | AnalysisFailure:
    parsed = parse_expression(query.comparison)
    if isinstance(parsed, ParseFailure):
        return _failure(
            "equivalence comparison must be a valid expression",
            f"queries[{position}].comparison",
            query.comparison,
            parsed,
        )
    if isinstance(parsed, (Equation, Relationship)):
        return _failure("equivalence comparison must be an expression", f"queries[{position}].comparison", query.comparison)
    return equivalence_answer(expression, parsed, reasoning)


def _unique_uses(values: tuple[object, ...]) -> tuple[object, ...]:
    seen: set[tuple[str, str]] = set()
    result: list[object] = []
    for value in values:
        name, relationship = value.name, value.relationship  # type: ignore[attr-defined]
        if (name, relationship) not in seen:
            seen.add((name, relationship))
            result.append(value)
    return tuple(result)
