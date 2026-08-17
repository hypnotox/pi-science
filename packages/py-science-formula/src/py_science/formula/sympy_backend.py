# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
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


@dataclass(frozen=True, slots=True)
class BoundedRationalDifference:
    left: Any
    right: Any
    numerator: Any
    denominator: Any
    symbols: tuple[Any, ...]


def bounded_rational_difference(
    left: Expression,
    right: Expression,
    *,
    max_intermediate_nodes: int = 4096,
    max_degree: int = 8,
    max_exponent: int = 32,
    max_coefficient_bits: int = 1024,
) -> BoundedRationalDifference | None:
    """Normalize one pre-allowlisted rational pair under explicit resource caps."""
    try:
        lhs: Any = _to_sympy(left)
        rhs: Any = _to_sympy(right)
        if sum(1 for _ in sympy.preorder_traversal(lhs)) > max_intermediate_nodes:
            return None
        if sum(1 for _ in sympy.preorder_traversal(rhs)) > max_intermediate_nodes:
            return None
        difference = sympy.cancel(lhs - rhs)
        if sum(1 for _ in sympy.preorder_traversal(difference)) > max_intermediate_nodes:
            return None
        numerator, denominator = sympy.fraction(difference)
        symbols = tuple(sorted(numerator.free_symbols | denominator.free_symbols, key=str))
        for value in (numerator, denominator):
            polynomial = sympy.Poly(value, *symbols) if symbols else None
            if polynomial is not None:
                if polynomial.total_degree() > max_degree:
                    return None
                if any(
                    abs(int(exponent)) > max_exponent
                    for monomial in polynomial.monoms()
                    for exponent in monomial
                ):
                    return None
                for coefficient in polynomial.coeffs():
                    numerator_part, denominator_part = sympy.fraction(coefficient)
                    if not numerator_part.is_Integer or not denominator_part.is_Integer:
                        return None
                    coefficient_bits = max(
                        abs(int(numerator_part)).bit_length(),
                        abs(int(denominator_part)).bit_length(),
                    )
                    if coefficient_bits > max_coefficient_bits:
                        return None
        return BoundedRationalDifference(lhs, rhs, numerator, denominator, symbols)
    except Exception:
        return None


def render(formula: Expression | Equation) -> NormalizedRendering:
    try:
        return _render_value(_to_sympy(formula))
    except Exception as error:
        raise NormalizationError("SymPy normalization failed") from error


def polynomial_degree(expression: Expression, variable: str) -> int | None:
    """Return a safe univariate polynomial degree without parsing submitted text."""
    try:
        symbol = cast(Callable[[str], SympyExpression], sympy.Symbol)(variable)
        value: Any = _to_sympy(expression)
        free_symbols = {str(item) for item in value.free_symbols}
        if free_symbols - {variable}:
            return None
        polynomial = value.as_poly(symbol)
        if polynomial is None:
            return None
        return int(polynomial.degree())
    except Exception:
        return None


def is_nondecreasing_polynomial(expression: Expression, variable: str) -> bool:
    """Prove endpoint ordering for polynomials with nonnegative derivative coefficients."""
    try:
        symbol: Any = cast(Callable[[str], SympyExpression], sympy.Symbol)(variable)
        value: Any = _to_sympy(expression)
        free_symbols = {str(item) for item in value.free_symbols}
        if free_symbols - {variable}:
            return False
        polynomial: Any = value.as_poly(symbol)
        if polynomial is None:
            return False
        derivative: Any = polynomial.diff()
        return all(bool(coefficient >= 0) for coefficient in derivative.all_coeffs())
    except Exception:
        return False


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
    if isinstance(formula, RationalLiteral):
        constructor = cast(Callable[[int, int], SympyExpression], sympy.Rational)
        return constructor(formula.numerator, formula.positive_denominator)
    if isinstance(formula, InfinityLiteral):
        return cast(SympyExpression, sympy.oo if formula.sign > 0 else -sympy.oo)
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
