# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportIndexIssue=false, reportUnusedImport=false
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
    Call,
    Equation,
    Formula,
    IndexedValue,
    IntegerLiteral,
    Sum,
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


type ParseResult = Formula | ParseFailure
MAX_INPUT_BYTES = 65_536
MAX_EXPRESSION_NODES = 4_096
MAX_EXPRESSION_DEPTH = 128
MAX_INTEGER_BITS = 3_402
MAX_DECIMAL_INTEGER_DIGITS = 1_024
_DECIMAL_INTEGER = re.compile(r"(?:0(?:_?0)*|[1-9](?:_?[0-9])*)\Z")


def parse_expression(source: str) -> ParseResult:
    """Parse data-only restricted SymPy spelling; it never evaluates source."""
    try:
        if len(source.encode("utf-8")) > MAX_INPUT_BYTES:
            return _failure(
                ParseFailureKind.TOO_COMPLEX,
                f"expression exceeds the maximum input size of {MAX_INPUT_BYTES} UTF-8 bytes",
            )
    except UnicodeEncodeError:
        return _failure(ParseFailureKind.MALFORMED, "expression is not valid UTF-8")
    integer_failure = _validate_decimal_integer_tokens(source)
    if integer_failure:
        return integer_failure
    try:
        root = ast.parse(source, mode="eval").body
        complexity_failure = _validate_complexity(root)
        if complexity_failure:
            return complexity_failure
        return _convert(root)
    except SyntaxError as error:
        return ParseFailure(
            ParseFailureKind.MALFORMED, error.msg, error.lineno, max((error.offset or 1) - 1, 0)
        )
    except RecursionError:
        return _failure(
            ParseFailureKind.TOO_COMPLEX, "expression nesting exceeds the supported limit"
        )


def _failure(kind: ParseFailureKind, message: str, node: ast.AST | None = None) -> ParseFailure:
    return ParseFailure(
        kind, message, getattr(node, "lineno", None), getattr(node, "col_offset", None)
    )


def _validate_decimal_integer_tokens(source: str) -> ParseFailure | None:
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if (
                token.type == tokenize.NUMBER
                and _DECIMAL_INTEGER.fullmatch(token.string)
                and sum(c.isdigit() for c in token.string) > MAX_DECIMAL_INTEGER_DIGITS
            ):
                return ParseFailure(
                    ParseFailureKind.TOO_COMPLEX,
                    "integer literal exceeds the maximum size of approximately 1024 decimal digits",
                    token.start[0],
                    token.start[1],
                )
    except (IndentationError, tokenize.TokenError):
        pass
    return None


def _validate_complexity(root: ast.expr) -> ParseFailure | None:
    stack: list[tuple[ast.AST, int]] = [(root, 1)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > MAX_EXPRESSION_DEPTH:
            return _failure(
                ParseFailureKind.TOO_COMPLEX,
                f"expression nesting exceeds the maximum depth of {MAX_EXPRESSION_DEPTH}",
                node,
            )
        if count > MAX_EXPRESSION_NODES:
            return _failure(ParseFailureKind.TOO_COMPLEX, "expression is too complex")
        integer = _integer_value(node)
        if integer is not None and integer.bit_length() > MAX_INTEGER_BITS:
            return _failure(
                ParseFailureKind.TOO_COMPLEX,
                "integer literal exceeds the maximum size of approximately 1024 decimal digits",
                node,
            )
        if not (isinstance(node, ast.UnaryOp) and _integer_value(node) is not None):
            stack.extend(
                (child, depth + 1)
                for child in ast.iter_child_nodes(node)
                if isinstance(child, ast.expr)
            )
    return None


def _integer_value(node: ast.AST) -> int | None:
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


def _convert(node: ast.expr) -> ParseResult:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return IntegerLiteral(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        return IntegerLiteral((-1 if isinstance(node.op, ast.USub) else 1) * node.operand.value)
    if isinstance(node, ast.Name):
        return Symbol(node.id)
    if isinstance(node, ast.BinOp):
        op = _binary_operator(node.op)
        if op:
            left, right = _convert(node.left), _convert(node.right)
            if isinstance(left, ParseFailure):
                return left
            if isinstance(right, ParseFailure):
                return right
            return BinaryExpression(op, left, right)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        values = node.slice.elts if isinstance(node.slice, ast.Tuple) else (node.slice,)
        if not values:
            return _failure(
                ParseFailureKind.UNSUPPORTED, "indexed values need at least one index", node
            )
        converted = tuple(_convert(value) for value in values)
        if any(isinstance(value, ParseFailure) for value in converted):
            return next(value for value in converted if isinstance(value, ParseFailure))
        return IndexedValue(node.value.id, converted)  # type: ignore[arg-type]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        if node.func.id == "Sum":
            if (
                len(node.args) != 2
                or not isinstance(node.args[1], ast.Tuple)
                or len(node.args[1].elts) != 3
                or not isinstance(node.args[1].elts[0], ast.Name)
            ):
                return _failure(
                    ParseFailureKind.UNSUPPORTED,
                    "Sum requires Sum(body, (index, lower, upper))",
                    node,
                )
            body, lower, upper = (
                _convert(node.args[0]),
                _convert(node.args[1].elts[1]),
                _convert(node.args[1].elts[2]),
            )
            if isinstance(body, ParseFailure):
                return body
            if isinstance(lower, ParseFailure):
                return lower
            if isinstance(upper, ParseFailure):
                return upper
            return Sum(body, node.args[1].elts[0].id, lower, upper)
        if node.func.id == "Eq":
            if len(node.args) != 2:
                return _failure(
                    ParseFailureKind.UNSUPPORTED, "Eq requires exactly two arguments", node
                )
            left, right = _convert(node.args[0]), _convert(node.args[1])
            if isinstance(left, ParseFailure):
                return left
            if isinstance(right, ParseFailure):
                return right
            if not isinstance(left, (Symbol, IndexedValue)):
                return _failure(
                    ParseFailureKind.UNSUPPORTED,
                    "equation left side must be a scalar or indexed result",
                    node.args[0],
                )
            return Equation(left, right)
        arguments = tuple(_convert(arg) for arg in node.args)
        if any(isinstance(arg, ParseFailure) for arg in arguments):
            return next(arg for arg in arguments if isinstance(arg, ParseFailure))
        return Call(node.func.id, arguments)  # type: ignore[arg-type]
    return _failure(
        ParseFailureKind.UNSUPPORTED, f"unsupported construct: {type(node).__name__}", node
    )


def _binary_operator(operator: ast.operator) -> BinaryOperator | None:
    return {
        ast.Add: BinaryOperator.ADD,
        ast.Sub: BinaryOperator.SUBTRACT,
        ast.Mult: BinaryOperator.MULTIPLY,
        ast.Div: BinaryOperator.DIVIDE,
        ast.Pow: BinaryOperator.POWER,
    }.get(type(operator))
