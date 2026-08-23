# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Repeated-call and reciprocal-reuse proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _EvaluationScope, _Occurrence
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    IntegerLiteral,
    expression_node_count,
)

from ..candidates import _CandidateDescriptor, _generated_replacement_descriptor, _smallest_scope


def propose(
    target: str, expression: Expression, occurrences: tuple[_Occurrence, ...], generated_name: str
) -> tuple[_CandidateDescriptor, ...]:
    grouped: dict[tuple[Expression, _EvaluationScope], list[_Occurrence]] = {}
    for occurrence in occurrences:
        repeated = occurrence.expression
        if isinstance(repeated, Call) or (
            isinstance(repeated, BinaryExpression)
            and repeated.operator is BinaryOperator.DIVIDE
            and isinstance(repeated.left, IntegerLiteral)
            and repeated.left.value == 1
        ):
            grouped.setdefault((repeated, occurrence.scope), []).append(occurrence)
    result = []
    for (repeated, scope), items in grouped.items():
        if len(items) < 2 or expression_node_count(repeated) < 2:
            continue
        kind = "repeated_call" if isinstance(repeated, Call) else "reciprocal_reuse"
        result.append(
            _generated_replacement_descriptor(
                kind=kind,
                target=target,
                original=expression,
                occurrences=tuple(items),
                generated_name=generated_name,
                intermediate_expression=repeated,
                intermediate_scope=_smallest_scope(repeated, scope),
            )
        )
    return tuple(result)
