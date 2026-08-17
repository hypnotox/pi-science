# ruff: noqa: E501
# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Bounded general-context query evaluation; it never contributes submitted work."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import sympy
from py_science.formula.exact_values import ExactRational, render_exact
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Equation,
    Expression,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
    Relationship,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
)
from py_science.formula.models import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisFailure,
    AsymptoticResult,
    ClosedFormQuery,
    ClosedFormResult,
    CounterexampleEvidence,
    EquivalenceQuery,
    EquivalenceResult,
    IdentityEvidence,
    Interpretation,
    LimitQuery,
    LimitResult,
    PropertiesQuery,
    PropertiesResult,
    PropertyCheck,
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
from py_science.formula.reasoning import ReasoningContext, collect_denominators
from py_science.formula.series import derive_closed_form
from py_science.formula.sympy_backend import bounded_rational_difference, render

UNIMPLEMENTED = "query kind is not implemented in this release slice"
MAX_TARGET_NODES = 512
MAX_SIBLING_SUMS = 8
MAX_EXPONENT = 32
MAX_COEFFICIENT_BITS = 1024
MAX_COUNTEREXAMPLE_STEPS = 256


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
    for position, query in enumerate(queries):
        if query.target is not None and query.target != target.target:
            return _failure("query target is unknown", f"queries[{position}].target")
        if isinstance(query, EquivalenceQuery):
            answer = _equivalence(query, target.expression, reasoning, position)
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
            expression, qualification = _property_expression(target.expression, reasoning)
            answers = tuple(
                afmm_tail_property_answer(target.expression, item, reasoning)
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
            answer = derive_closed_form(target.expression, reasoning)
            result = ClosedFormResult(name=query.name, target=target.target, normalized_target=target.interpretation, summary="qualified bounded series closed form", answers=(answer,))
        elif isinstance(query, LimitQuery):
            expression, qualification = _property_expression(target.expression, reasoning)
            answer = _with_closed_form_qualification(limit_answer(expression, query, reasoning), qualification)
            result = LimitResult(name=query.name, target=target.target, normalized_target=target.interpretation, summary="bounded exact directional limit", answers=(answer,))
        else:
            result = AsymptoticResult(name=query.name, target=target.target, normalized_target=target.interpretation, summary=UNIMPLEMENTED, answers=(_unresolved(),))
        results.append(result)
    return tuple(results)


def _property_expression(
    expression: Expression, reasoning: ReasoningContext | None
) -> tuple[Expression, QueryAnswer | None]:
    """Replace only a Task-3-proved series before the Task-4 rational rules."""
    if not any(isinstance(item, Sum) for item in _walk(expression)):
        return expression, None
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


def _unresolved(check: PropertyCheck | None = None) -> QueryAnswer:
    return QueryAnswer(check=check, conclusion="unresolved", blockers=(UNIMPLEMENTED,))


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
    if reasoning is None:
        return _unresolved_with("query reasoning exceeds its bound")
    if not _allowed_rational(expression) or not _allowed_rational(parsed):
        return _unresolved_with("query family is unsupported")
    original_symbols = _symbol_names(expression) | _symbol_names(parsed)
    try:
        left = reasoning.apply(expression)
        right = reasoning.apply(parsed)
    except Exception:
        return _unresolved_with("query reasoning exceeds its bound")
    if not _allowed_rational(left) or not _allowed_rational(right):
        return _unresolved_with("query family is unsupported")
    symbols = _symbol_names(left) | _symbol_names(right)
    relevant_symbols = symbols | original_symbols
    unsupported = reasoning.relevant_unsupported(relevant_symbols)
    original_denominators = (*collect_denominators(left), *collect_denominators(right))
    normalized = bounded_rational_difference(left, right)
    if normalized is None:
        return _unresolved_with("query rational normalization exceeds its bound", unsupported)
    conditions: list[str] = []
    obligation_uses = []
    for denominator in original_denominators:
        denominator_normalized = bounded_rational_difference(
            denominator,
            IntegerLiteral(0),
        )
        if denominator_normalized is None:
            return _unresolved_with("query denominator exceeds its bound", unsupported)
        if denominator_normalized.numerator == 0:
            return _unresolved_with("query denominator is identically zero", unsupported)
        try:
            statement = f"{render(denominator).sympy} != 0"
        except Exception:
            return _unresolved_with("query denominator cannot be rendered", unsupported)
        if len(statement) > 4096:
            return _unresolved_with("query denominator rendering exceeds its bound", unsupported)
        if statement not in conditions:
            conditions.append(statement)
        proved, uses = reasoning.prove_nonzero(denominator)
        if proved:
            obligation_uses.extend(uses)
    used = reasoning.relevant_uses(relevant_symbols, include_facts=bool(original_denominators))
    used = _unique_uses((*used, *obligation_uses))
    if len(used) > 128:
        return _unresolved_with("query assumption provenance exceeds its bound", unsupported)
    if normalized.numerator == 0:
        conclusion = "proved_under_assumptions" if used or conditions else "proved"
        return QueryAnswer(
            conclusion=conclusion,
            conditions=tuple(conditions),
            assumptions_used=used,
            relevant_unsupported_assumptions=unsupported,
            evidence=IdentityEvidence(statement="normalized difference is zero"),
        )
    if (
        not normalized.left.free_symbols
        and not normalized.right.free_symbols
        and normalized.numerator.is_number
    ):
        if not normalized.left.is_Rational or not normalized.right.is_Rational:
            return _unresolved_with("query evidence is not a finite exact value", unsupported)
        target_rendered = str(normalized.left)
        comparison_rendered = str(normalized.right)
        if max(len(target_rendered), len(comparison_rendered)) > 4096:
            return _unresolved_with("query evidence rendering exceeds its bound", unsupported)
        return QueryAnswer(
            conclusion="disproved",
            conditions=tuple(conditions),
            assumptions_used=used,
            relevant_unsupported_assumptions=unsupported,
            evidence=CounterexampleEvidence(
                substitutions={},
                target_value=target_rendered,
                comparison_value=comparison_rendered,
            ),
        )
    candidates = (
        sympy.Rational(0), sympy.Rational(1), sympy.Rational(-1),
        sympy.Rational(2), sympy.Rational(-2), sympy.Rational(1, 2), sympy.Rational(-1, 2),
    )
    steps = 0
    for items in product(candidates, repeat=len(normalized.symbols)):
        steps += 1
        if steps > MAX_COUNTEREXAMPLE_STEPS:
            break
        values = dict(zip(normalized.symbols, items, strict=True))
        try:
            if not reasoning.assignment_valid(values):
                continue
            if any(_sympy_denominator(denominator).subs(values) == 0 for denominator in original_denominators):
                continue
            if normalized.denominator.subs(values) == 0 or normalized.numerator.subs(values) == 0:
                continue
            target_value = normalized.left.subs(values)
            comparison_value = normalized.right.subs(values)
            if target_value.free_symbols or comparison_value.free_symbols:
                continue
            if not target_value.is_Rational or not comparison_value.is_Rational:
                continue
            target_rendered = str(target_value)
            comparison_rendered = str(comparison_value)
            if max(len(target_rendered), len(comparison_rendered)) > 4096:
                return _unresolved_with("query evidence rendering exceeds its bound", unsupported)
            candidate_uses = reasoning.relevant_uses(relevant_symbols, include_facts=True)
            if len(candidate_uses) > 128:
                return _unresolved_with("query assumption provenance exceeds its bound", unsupported)
            return QueryAnswer(
                conclusion="disproved",
                conditions=tuple(conditions),
                assumptions_used=candidate_uses,
                relevant_unsupported_assumptions=unsupported,
                evidence=CounterexampleEvidence(
                    substitutions={str(key): _canonical_exact(value) for key, value in values.items()},
                    target_value=target_rendered,
                    comparison_value=comparison_rendered,
                ),
            )
        except Exception:
            continue
    return _unresolved_with("no bounded counterexample satisfies the supported assumptions", unsupported)


def _allowed_rational(expression: Expression) -> bool:
    if expression_node_count(expression) > MAX_TARGET_NODES:
        return False
    sibling_sums = sum(isinstance(child, Sum) for child in expression_children(expression))
    if sibling_sums > MAX_SIBLING_SUMS:
        return False
    if isinstance(expression, (InfinityLiteral, Sum)):
        return False
    if isinstance(expression, IntegerLiteral):
        return expression.value.bit_length() <= MAX_COEFFICIENT_BITS
    if isinstance(expression, RationalLiteral):
        return max(abs(expression.numerator).bit_length(), expression.positive_denominator.bit_length()) <= MAX_COEFFICIENT_BITS
    if isinstance(expression, Symbol):
        return True
    if not isinstance(expression, BinaryExpression):
        return False
    if expression.operator is BinaryOperator.POWER:
        exponent = expression.right
        if not isinstance(exponent, (IntegerLiteral, RationalLiteral)):
            return False
        value = exponent.value if isinstance(exponent, IntegerLiteral) else (exponent.numerator if exponent.positive_denominator == 1 else MAX_EXPONENT + 1)
        if abs(value) > MAX_EXPONENT:
            return False
    return all(_allowed_rational(child) for child in expression_children(expression))


def _symbol_names(expression: Expression) -> set[str]:
    names = {expression.name} if isinstance(expression, Symbol) else set()
    for child in expression_children(expression):
        names |= _symbol_names(child)
    return names


def _sympy_denominator(expression: Expression) -> Any:
    normalized = bounded_rational_difference(expression, IntegerLiteral(0))
    if normalized is None:
        raise ValueError("unsupported denominator")
    return normalized.left


def _canonical_exact(value: Any) -> str:
    return render_exact(ExactRational(int(value.p), int(value.q)))


def _unique_uses(values: tuple[Any, ...]) -> tuple[Any, ...]:
    seen: set[tuple[str, str]] = set()
    result = []
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _unresolved_with(blocker: str, unsupported: tuple[str, ...] = ()) -> QueryAnswer:
    return QueryAnswer(conclusion="unresolved", blockers=(blocker,), relevant_unsupported_assumptions=unsupported)
