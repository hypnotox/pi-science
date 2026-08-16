from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    IndexedValue,
    IntegerLiteral,
    Sum,
    Symbol,
)


class SympyExpression(Protocol):
    def __add__(self, other: object, /) -> SympyExpression: ...

    def __sub__(self, other: object, /) -> SympyExpression: ...

    def __mul__(self, other: object, /) -> SympyExpression: ...

    def __truediv__(self, other: object, /) -> SympyExpression: ...

    def __pow__(
        self,
        other: object,
        modulo: object | None = None,
        /,
    ) -> SympyExpression: ...


class SympyIndexedBase(Protocol):
    def __getitem__(self, key: object, /) -> SympyExpression: ...


class NormalizationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedRendering:
    sympy: str
    latex: str


def render(formula: Expression | Equation) -> NormalizedRendering:
    try:
        return _render_value(_to_sympy(formula))
    except Exception as error:
        raise NormalizationError("SymPy normalization failed") from error


def render_system(equations: tuple[Equation, ...]) -> NormalizedRendering:
    try:
        constructor = cast(Callable[..., SympyExpression], sympy.Tuple)
        return _render_value(constructor(*(_to_sympy(equation) for equation in equations)))
    except Exception as error:
        raise NormalizationError("SymPy normalization failed") from error


def _render_value(value: SympyExpression) -> NormalizedRendering:
    return NormalizedRendering(
        sympy=str(value),
        latex=cast(str, sympy.latex(value)),
    )


def _to_sympy(formula: Expression | Equation) -> SympyExpression:
    if isinstance(formula, IntegerLiteral):
        constructor = cast(Callable[[int], SympyExpression], sympy.Integer)
        return constructor(formula.value)
    if isinstance(formula, Symbol):
        constructor = cast(Callable[[str], SympyExpression], sympy.Symbol)
        return constructor(formula.name)
    if isinstance(formula, IndexedValue):
        constructor = cast(Callable[[str], SympyIndexedBase], sympy.IndexedBase)
        base = constructor(formula.name)
        indices = tuple(_to_sympy(index) for index in formula.indices)
        return base[indices[0] if len(indices) == 1 else indices]
    if isinstance(formula, Call):
        arguments = tuple(_to_sympy(argument) for argument in formula.arguments)
        if formula.name == "Max":
            constructor = cast(Callable[..., SympyExpression], sympy.Max)
        else:
            function_factory = cast(Callable[[str], Callable[..., SympyExpression]], sympy.Function)
            constructor = function_factory(formula.name)
        return constructor(*arguments)
    if isinstance(formula, Sum):
        constructor = cast(Callable[..., SympyExpression], sympy.Sum)
        symbol_constructor = cast(Callable[[str], SympyExpression], sympy.Symbol)
        return constructor(
            _to_sympy(formula.body),
            (
                symbol_constructor(formula.index),
                _to_sympy(formula.lower),
                _to_sympy(formula.upper),
            ),
        )
    if isinstance(formula, Equation):
        constructor = cast(Callable[..., SympyExpression], sympy.Eq)
        return constructor(
            _to_sympy(formula.left),
            _to_sympy(formula.right),
            evaluate=False,
        )
    return _binary_to_sympy(formula)


def _binary_to_sympy(expression: BinaryExpression) -> SympyExpression:
    left = _to_sympy(expression.left)
    right = _to_sympy(expression.right)
    if expression.operator is BinaryOperator.ADD:
        return left + right
    if expression.operator is BinaryOperator.SUBTRACT:
        return left - right
    if expression.operator is BinaryOperator.MULTIPLY:
        return left * right
    if expression.operator is BinaryOperator.DIVIDE:
        return left / right
    power = cast(Callable[..., SympyExpression], sympy.Pow)
    unevaluated = cast(Callable[[object], SympyExpression], sympy.UnevaluatedExpr)
    return unevaluated(power(left, right, evaluate=False))
