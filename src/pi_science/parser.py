from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum

from pi_science.expressions import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    IntegerLiteral,
    Symbol,
)


class ParseFailureKind(StrEnum):
    MALFORMED = "malformed"
    UNSUPPORTED = "unsupported"
    TOO_COMPLEX = "too_complex"


@dataclass(frozen=True, slots=True)
class ParseFailure:
    kind: ParseFailureKind
    message: str
    line: int | None
    column: int | None


type ParseResult = Expression | ParseFailure


def parse_expression(source: str) -> ParseResult:
    try:
        parsed = ast.parse(source, mode="eval")
        return _convert(parsed.body)
    except SyntaxError as error:
        return ParseFailure(
            kind=ParseFailureKind.MALFORMED,
            message=error.msg,
            line=error.lineno,
            column=max((error.offset or 1) - 1, 0),
        )
    except RecursionError:
        return ParseFailure(
            kind=ParseFailureKind.TOO_COMPLEX,
            message="expression nesting exceeds the supported limit",
            line=None,
            column=None,
        )


def _convert(node: ast.expr) -> ParseResult:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return IntegerLiteral(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        return IntegerLiteral(sign * node.operand.value)
    if isinstance(node, ast.Name):
        return Symbol(node.id)
    if isinstance(node, ast.BinOp):
        operator = _binary_operator(node.op)
        if operator is not None:
            left = _convert(node.left)
            if isinstance(left, ParseFailure):
                return left
            right = _convert(node.right)
            if isinstance(right, ParseFailure):
                return right
            return BinaryExpression(operator, left, right)
    return ParseFailure(
        kind=ParseFailureKind.UNSUPPORTED,
        message=f"unsupported construct: {type(node).__name__}",
        line=getattr(node, "lineno", None),
        column=getattr(node, "col_offset", None),
    )


def _binary_operator(operator: ast.operator) -> BinaryOperator | None:
    if isinstance(operator, ast.Add):
        return BinaryOperator.ADD
    if isinstance(operator, ast.Sub):
        return BinaryOperator.SUBTRACT
    if isinstance(operator, ast.Mult):
        return BinaryOperator.MULTIPLY
    if isinstance(operator, ast.Div):
        return BinaryOperator.DIVIDE
    if isinstance(operator, ast.Pow):
        return BinaryOperator.POWER
    return None
