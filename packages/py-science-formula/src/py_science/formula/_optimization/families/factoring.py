# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Bounded factoring proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Equation,
    Expression,
    Relationship,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.sympy_backend import bounded_factor_candidate

from ..candidates import _CandidateDescriptor, _replacement_descriptor


def _factor_term(expression: Expression) -> tuple[Expression, Expression] | None:
    if (
        not isinstance(expression, BinaryExpression)
        or expression.operator is not BinaryOperator.MULTIPLY
    ):
        return None
    return expression.left, expression.right


def _factored(expression: Expression) -> Expression | None:
    if not isinstance(expression, BinaryExpression) or expression.operator not in {
        BinaryOperator.ADD,
        BinaryOperator.SUBTRACT,
    }:
        return None
    left = _factor_term(expression.left)
    right = _factor_term(expression.right)
    if left is None or right is None:
        return None
    common: Expression | None = None
    left_rest: Expression | None = None
    right_rest: Expression | None = None
    for left_position, left_item in enumerate(left):
        for right_position, right_item in enumerate(right):
            if left_item == right_item:
                common = left_item
                left_rest = left[1 - left_position]
                right_rest = right[1 - right_position]
                break
        if common is not None:
            break
    if common is None or left_rest is None or right_rest is None:
        return None
    rendered = bounded_factor_candidate(expression)
    if rendered is None:
        return None
    parsed = parse_expression(rendered)
    if isinstance(parsed, (ParseFailure, Equation, Relationship)):
        return None
    return parsed


def propose(
    target: str, expression: Expression, occurrence: _Occurrence
) -> tuple[_CandidateDescriptor, ...]:
    replacement = _factored(occurrence.expression)
    return (
        ()
        if replacement is None
        else (
            _replacement_descriptor(
                kind="factoring",
                target=target,
                original=expression,
                occurrences=(occurrence,),
                replacement=replacement,
            ),
        )
    )
