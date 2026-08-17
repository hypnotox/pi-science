from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from enum import StrEnum

from py_science.formula.exact_values import parse_exact_scalar
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    Formula,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
    Relationship,
    RelationshipOperator,
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
    """Parse restricted SymPy spelling as data without evaluating submitted text."""
    try:
        encoded_source = source.encode("utf-8")
    except UnicodeEncodeError:
        return _failure(ParseFailureKind.MALFORMED, "expression is not valid UTF-8")
    if len(encoded_source) > MAX_INPUT_BYTES:
        return _failure(
            ParseFailureKind.TOO_COMPLEX,
            f"expression exceeds the maximum input size of {MAX_INPUT_BYTES} UTF-8 bytes",
        )

    integer_failure = _validate_decimal_integer_tokens(source)
    if integer_failure is not None:
        return integer_failure
    try:
        root = ast.parse(source, mode="eval").body
        complexity_failure = _validate_complexity(root)
        if complexity_failure is not None:
            return complexity_failure
        return _convert(root)
    except SyntaxError as error:
        return ParseFailure(
            ParseFailureKind.MALFORMED,
            error.msg,
            error.lineno,
            max((error.offset or 1) - 1, 0),
        )
    except RecursionError:
        return _failure(
            ParseFailureKind.TOO_COMPLEX,
            "expression nesting exceeds the supported limit",
        )


def _failure(
    kind: ParseFailureKind,
    message: str,
    node: ast.AST | None = None,
) -> ParseFailure:
    return ParseFailure(
        kind,
        message,
        getattr(node, "lineno", None),
        getattr(node, "col_offset", None),
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
                return ParseFailure(
                    ParseFailureKind.TOO_COMPLEX,
                    "integer literal exceeds the maximum size of approximately 1024 decimal digits",
                    token.start[0],
                    token.start[1],
                )
    except (IndentationError, tokenize.TokenError):
        return None
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
        if not (isinstance(node, ast.UnaryOp) and integer is not None):
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
    if isinstance(node, ast.Constant) and type(node.value) is float:
        value = parse_exact_scalar(str(node.value))
        if value is None:
            return _failure(ParseFailureKind.TOO_COMPLEX, "decimal literal exceeds exact-value bounds", node)  # noqa: E501
        return RationalLiteral(value.numerator, value.denominator)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        return IntegerLiteral(sign * node.operand.value)
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Name) and node.operand.id == "oo"):
        return InfinityLiteral(-1)
    if isinstance(node, ast.Name):
        if node.id == "oo":
            return InfinityLiteral(1)
        return _symbol(node)
    if isinstance(node, ast.BinOp):
        return _convert_binary(node)
    if isinstance(node, ast.Subscript):
        return _convert_indexed(node)
    if isinstance(node, ast.Call):
        return _convert_call(node)
    if isinstance(node, ast.Compare):
        return _convert_relationship(node)
    return _failure(
        ParseFailureKind.UNSUPPORTED,
        f"unsupported construct: {type(node).__name__}",
        node,
    )


def _symbol(node: ast.Name) -> Symbol | ParseFailure:
    if node.id.startswith("__"):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "dunder names are not supported mathematical identifiers",
            node,
        )
    return Symbol(node.id)


def _convert_relationship(node: ast.Compare) -> ParseResult:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return _failure(
            ParseFailureKind.UNSUPPORTED, "chained relationships are not supported", node
        )
    comparison = node.ops[0]
    if isinstance(comparison, ast.Eq):
        operator = RelationshipOperator.EQUAL
    elif isinstance(comparison, ast.Lt):
        operator = RelationshipOperator.LESS
    elif isinstance(comparison, ast.LtE):
        operator = RelationshipOperator.LESS_EQUAL
    elif isinstance(comparison, ast.Gt):
        operator = RelationshipOperator.GREATER
    elif isinstance(comparison, ast.GtE):
        operator = RelationshipOperator.GREATER_EQUAL
    else:
        operator = None
    if operator is None:
        return _failure(ParseFailureKind.UNSUPPORTED, "unsupported relationship operator", node)
    left = _convert(node.left)
    right = _convert(node.comparators[0])
    if isinstance(left, ParseFailure):
        return left
    if isinstance(right, ParseFailure):
        return right
    if isinstance(left, (Equation, Relationship)) or isinstance(right, (Equation, Relationship)):
        return _failure(ParseFailureKind.UNSUPPORTED, "relationships cannot be nested", node)
    return Relationship(operator, left, right)


def _convert_binary(node: ast.BinOp) -> ParseResult:
    operator = _binary_operator(node.op)
    if operator is None:
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            f"unsupported construct: {type(node.op).__name__}",
            node,
        )
    left = _convert(node.left)
    if isinstance(left, ParseFailure):
        return left
    right = _convert(node.right)
    if isinstance(right, ParseFailure):
        return right
    if isinstance(left, (Equation, Relationship)) or isinstance(right, (Equation, Relationship)):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "Eq cannot be nested inside an expression",
            node,
        )
    return BinaryExpression(operator, left, right)


def _convert_indexed(node: ast.Subscript) -> ParseResult:
    if not isinstance(node.value, ast.Name):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "indexed values require a named base",
            node,
        )
    base = _symbol(node.value)
    if isinstance(base, ParseFailure):
        return base
    values: tuple[ast.expr, ...] = (
        tuple(node.slice.elts) if isinstance(node.slice, ast.Tuple) else (node.slice,)
    )
    if not values:
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "indexed values need at least one index",
            node,
        )
    indices: list[Expression] = []
    for value in values:
        converted = _convert(value)
        if isinstance(converted, ParseFailure):
            return converted
        if isinstance(converted, (Equation, Relationship)):
            return _failure(
                ParseFailureKind.UNSUPPORTED,
                "relationships cannot be used as an index",
                value,
            )
        indices.append(converted)
    return IndexedValue(base.name, tuple(indices))


def _convert_call(node: ast.Call) -> ParseResult:
    if not isinstance(node.func, ast.Name):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "function calls require an ordinary named target",
            node,
        )
    function = _symbol(node.func)
    if isinstance(function, ParseFailure):
        return function
    if node.keywords or any(isinstance(argument, ast.Starred) for argument in node.args):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "function calls accept positional arguments only",
            node,
        )
    if function.name == "Sum":
        return _convert_sum(node)
    if function.name == "Eq":
        return _convert_equation(node)
    if function.name == "Max":
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "Max is reserved for analyzer aggregate-work semantics",
            node,
        )

    arguments: list[Expression] = []
    for argument in node.args:
        converted = _convert(argument)
        if isinstance(converted, ParseFailure):
            return converted
        if isinstance(converted, (Equation, Relationship)):
            return _failure(
                ParseFailureKind.UNSUPPORTED,
                "relationships cannot be used as a function argument",
                argument,
            )
        arguments.append(converted)
    return Call(function.name, tuple(arguments))


def _convert_sum(node: ast.Call) -> ParseResult:
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
    index_symbol = _symbol(node.args[1].elts[0])
    if isinstance(index_symbol, ParseFailure):
        return index_symbol
    converted_parts: list[Expression] = []
    for part in (node.args[0], node.args[1].elts[1], node.args[1].elts[2]):
        converted = _convert(part)
        if isinstance(converted, ParseFailure):
            return converted
        if isinstance(converted, (Equation, Relationship)):
            return _failure(
                ParseFailureKind.UNSUPPORTED,
                "relationships cannot be nested inside Sum",
                part,
            )
        converted_parts.append(converted)
    body, lower, upper = converted_parts
    return Sum(body, index_symbol.name, lower, upper)


def _convert_equation(node: ast.Call) -> ParseResult:
    if len(node.args) != 2:
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "Eq requires exactly two arguments",
            node,
        )
    left = _convert(node.args[0])
    if isinstance(left, ParseFailure):
        return left
    right = _convert(node.args[1])
    if isinstance(right, ParseFailure):
        return right
    if not isinstance(left, (Symbol, IndexedValue)):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "equation left side must be a scalar or indexed result",
            node.args[0],
        )
    if isinstance(right, (Equation, Relationship)):
        return _failure(
            ParseFailureKind.UNSUPPORTED,
            "Eq cannot be nested inside Eq",
            node.args[1],
        )
    return Equation(left, right)


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
