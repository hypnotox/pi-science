# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportIndexIssue=false, reportUnusedImport=false
from __future__ import annotations

from dataclasses import dataclass

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.expressions import (
    BinaryOperator,
    Call,
    Equation,
    Expression,
    IndexedValue,
    IntegerLiteral,
    Sum,
    Symbol,
)


class NormalizationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedRendering:
    sympy: str
    latex: str


def render(expression: Expression | Equation) -> NormalizedRendering:
    try:
        value = _to_sympy(expression)
        return NormalizedRendering(str(value), str(sympy.latex(value)))
    except Exception as error:
        raise NormalizationError("SymPy normalization failed") from error


def _to_sympy(expression: Expression | Equation):
    if isinstance(expression, IntegerLiteral):
        return sympy.Integer(expression.value)
    if isinstance(expression, Symbol):
        return sympy.Symbol(expression.name)
    if isinstance(expression, IndexedValue):
        return sympy.IndexedBase(expression.name)[tuple(_to_sympy(i) for i in expression.indices)]
    if isinstance(expression, Call):
        return sympy.Function(expression.name)(*(_to_sympy(a) for a in expression.arguments))
    if isinstance(expression, Sum):
        return sympy.Sum(
            _to_sympy(expression.body),
            (
                sympy.Symbol(expression.index),
                _to_sympy(expression.lower),
                _to_sympy(expression.upper),
            ),
        )
    if isinstance(expression, Equation):
        return sympy.Eq(_to_sympy(expression.left), _to_sympy(expression.right), evaluate=False)
    left, right = _to_sympy(expression.left), _to_sympy(expression.right)
    if expression.operator is BinaryOperator.ADD:
        return left + right
    if expression.operator is BinaryOperator.SUBTRACT:
        return left - right
    if expression.operator is BinaryOperator.MULTIPLY:
        return left * right
    if expression.operator is BinaryOperator.DIVIDE:
        return left / right
    return sympy.UnevaluatedExpr(sympy.Pow(left, right, evaluate=False))
