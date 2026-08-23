# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Neutral-operation removal proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    IntegerLiteral,
)

from ..candidates import _CandidateDescriptor, _replacement_descriptor


def _neutral_replacement(expression: Expression) -> Expression | None:
    if not isinstance(expression, BinaryExpression):
        return None
    left, right = expression.left, expression.right
    if isinstance(right, IntegerLiteral):
        if right.value == 0 and expression.operator in {
            BinaryOperator.ADD,
            BinaryOperator.SUBTRACT,
        }:
            return left
        if right.value == 1 and expression.operator in {
            BinaryOperator.MULTIPLY,
            BinaryOperator.DIVIDE,
            BinaryOperator.POWER,
        }:
            return left
    if isinstance(left, IntegerLiteral):
        if left.value == 0 and expression.operator is BinaryOperator.ADD:
            return right
        if left.value == 1 and expression.operator is BinaryOperator.MULTIPLY:
            return right
    return None


def propose(
    target: str, expression: Expression, occurrence: _Occurrence
) -> tuple[_CandidateDescriptor, ...]:
    replacement = _neutral_replacement(occurrence.expression)
    return (
        ()
        if replacement is None
        else (
            _replacement_descriptor(
                kind="redundant_operation_removal",
                target=target,
                original=expression,
                occurrences=(occurrence,),
                replacement=replacement,
            ),
        )
    )
