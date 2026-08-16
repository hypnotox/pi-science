from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from enum import StrEnum

from py_science.formula.expressions import (
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

MAX_INPUT_BYTES = 65_536
MAX_EXPRESSION_NODES = 4_096
MAX_EXPRESSION_DEPTH = 128
MAX_INTEGER_BITS = 3_402
MAX_DECIMAL_INTEGER_DIGITS = 1_024
_DECIMAL_INTEGER = re.compile(r"(?:0(?:_?0)*|[1-9](?:_?[0-9])*)\Z")


def parse_expression(source: str) -> ParseResult:
    try:
        encoded_source = source.encode("utf-8")
    except UnicodeEncodeError:
        return ParseFailure(
            kind=ParseFailureKind.MALFORMED,
            message="expression is not valid UTF-8",
            line=None,
            column=None,
        )
    if len(encoded_source) > MAX_INPUT_BYTES:
        return ParseFailure(
            kind=ParseFailureKind.TOO_COMPLEX,
            message=(
                "expression exceeds the maximum input size of "
                f"{MAX_INPUT_BYTES} UTF-8 bytes"
            ),
            line=None,
            column=None,
        )

    integer_failure = _validate_decimal_integer_tokens(source)
    if integer_failure is not None:
        return integer_failure

    try:
        parsed = ast.parse(source, mode="eval")
        complexity_failure = _validate_complexity(parsed.body)
        if complexity_failure is not None:
            return complexity_failure
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


def _validate_decimal_integer_tokens(source: str) -> ParseFailure | None:
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if (
                token.type == tokenize.NUMBER
                and _DECIMAL_INTEGER.fullmatch(token.string) is not None
                and sum(character.isdigit() for character in token.string)
                > MAX_DECIMAL_INTEGER_DIGITS
            ):
                return _integer_too_large(token.start[0], token.start[1])
    except (IndentationError, tokenize.TokenError):
        # ast.parse remains authoritative for malformed syntax and its location.
        return None
    return None


def _validate_complexity(root: ast.expr) -> ParseFailure | None:
    stack: list[tuple[ast.expr, int]] = [(root, 1)]
    node_count = 0
    while stack:
        node, depth = stack.pop()
        node_count += 1
        if depth > MAX_EXPRESSION_DEPTH:
            return ParseFailure(
                kind=ParseFailureKind.TOO_COMPLEX,
                message=(
                    "expression nesting exceeds the maximum depth of "
                    f"{MAX_EXPRESSION_DEPTH}"
                ),
                line=getattr(node, "lineno", None),
                column=getattr(node, "col_offset", None),
            )
        if node_count > MAX_EXPRESSION_NODES:
            return ParseFailure(
                kind=ParseFailureKind.TOO_COMPLEX,
                message="expression is too complex",
                line=None,
                column=None,
            )
        integer = _integer_value(node)
        if integer is not None and integer.bit_length() > MAX_INTEGER_BITS:
            return _integer_too_large(
                getattr(node, "lineno", None),
                getattr(node, "col_offset", None),
            )
        stack.extend((child, depth + 1) for child in _complexity_children(node))
    return None


def _complexity_children(node: ast.expr) -> tuple[ast.expr, ...]:
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        return ()
    return tuple(
        child for child in ast.iter_child_nodes(node) if isinstance(child, ast.expr)
    )


def _integer_value(node: ast.expr) -> int | None:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        return node.operand.value
    return None


def _integer_too_large(line: int | None, column: int | None) -> ParseFailure:
    return ParseFailure(
        kind=ParseFailureKind.TOO_COMPLEX,
        message=(
            "integer literal exceeds the maximum size of approximately "
            "1024 decimal digits"
        ),
        line=line,
        column=column,
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
