from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BinaryOperator(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


@dataclass(frozen=True, slots=True)
class IntegerLiteral:
    value: int


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str


@dataclass(frozen=True, slots=True)
class IndexedValue:
    name: str
    indices: tuple[Expression, ...]


@dataclass(frozen=True, slots=True)
class Call:
    name: str
    arguments: tuple[Expression, ...]


@dataclass(frozen=True, slots=True)
class Sum:
    body: Expression
    index: str
    lower: Expression
    upper: Expression


@dataclass(frozen=True, slots=True)
class BinaryExpression:
    operator: BinaryOperator
    left: Expression
    right: Expression


@dataclass(frozen=True, slots=True)
class Equation:
    left: Symbol | IndexedValue
    right: Expression


type Expression = IntegerLiteral | Symbol | IndexedValue | Call | Sum | BinaryExpression
type Formula = Expression | Equation


def expression_children(expression: Expression) -> tuple[Expression, ...]:
    if isinstance(expression, BinaryExpression):
        return (expression.left, expression.right)
    if isinstance(expression, IndexedValue):
        return expression.indices
    if isinstance(expression, Call):
        return expression.arguments
    if isinstance(expression, Sum):
        return (expression.lower, expression.upper, expression.body)
    return ()


def expression_node_count(expression: Expression) -> int:
    return 1 + sum(expression_node_count(child) for child in expression_children(expression))


def substitute(expression: Expression, replacements: dict[str, Expression]) -> Expression:
    if isinstance(expression, Symbol):
        return replacements.get(expression.name, expression)
    if isinstance(expression, IndexedValue):
        return IndexedValue(
            expression.name,
            tuple(substitute(index, replacements) for index in expression.indices),
        )
    if isinstance(expression, Call):
        return Call(
            expression.name,
            tuple(substitute(argument, replacements) for argument in expression.arguments),
        )
    if isinstance(expression, Sum):
        scoped = {name: value for name, value in replacements.items() if name != expression.index}
        return Sum(
            substitute(expression.body, scoped),
            expression.index,
            substitute(expression.lower, replacements),
            substitute(expression.upper, replacements),
        )
    if isinstance(expression, BinaryExpression):
        return BinaryExpression(
            expression.operator,
            substitute(expression.left, replacements),
            substitute(expression.right, replacements),
        )
    return expression
