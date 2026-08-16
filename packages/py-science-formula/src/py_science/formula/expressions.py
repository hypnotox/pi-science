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
class BinaryExpression:
    operator: BinaryOperator
    left: Expression
    right: Expression


type Expression = IntegerLiteral | Symbol | BinaryExpression
