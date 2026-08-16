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
