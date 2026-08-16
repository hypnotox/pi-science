from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

import sympy  # pyright: ignore[reportMissingTypeStubs]

from pi_science.expressions import BinaryOperator, Expression, IntegerLiteral, Symbol


class SympyExpression(Protocol):
    def __add__(self, other: object, /) -> SympyExpression: ...

    def __sub__(self, other: object, /) -> SympyExpression: ...

    def __mul__(self, other: object, /) -> SympyExpression: ...

    def __truediv__(self, other: object, /) -> SympyExpression: ...

    def __pow__(self, other: object, modulo: object | None = None, /) -> SympyExpression: ...


@dataclass(frozen=True, slots=True)
class NormalizedRendering:
    sympy: str
    latex: str


def render(expression: Expression) -> NormalizedRendering:
    normalized = _to_sympy(expression)
    return NormalizedRendering(
        sympy=str(normalized),
        latex=cast(str, sympy.latex(normalized)),
    )


def _to_sympy(expression: Expression) -> SympyExpression:
    if isinstance(expression, IntegerLiteral):
        return cast(SympyExpression, sympy.Integer(expression.value))
    if isinstance(expression, Symbol):
        return cast(SympyExpression, sympy.Symbol(expression.name))

    left = _to_sympy(expression.left)
    right = _to_sympy(expression.right)
    match expression.operator:
        case BinaryOperator.ADD:
            return left + right
        case BinaryOperator.SUBTRACT:
            return left - right
        case BinaryOperator.MULTIPLY:
            return left * right
        case BinaryOperator.DIVIDE:
            return left / right
        case BinaryOperator.POWER:
            return left**right
