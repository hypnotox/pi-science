"""Bounded policy for acyclic affine equation output domains."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol

from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    IntegerLiteral,
    RationalLiteral,
    Symbol,
    expression_children,
)
from py_science.formula.models import RelationshipUse


@dataclass(frozen=True, slots=True)
class OutputDomain:
    index: str
    lower: Expression
    upper: Expression
    lower_path: str
    upper_path: str
    dependencies: frozenset[str]


@dataclass(frozen=True, slots=True)
class DomainDiagnostic:
    message: str
    path: str


class AffineReasoner(Protocol):
    def prove_nonnegative(
        self, expression: Expression
    ) -> tuple[bool, tuple[RelationshipUse, ...]]: ...


def build_output_domains(
    bounds: dict[str, tuple[Expression, Expression]],
    lhs_order: tuple[str, ...],
    equation_position: int,
    declared_integer_symbols: frozenset[str],
) -> tuple[tuple[OutputDomain, ...], tuple[str, ...]] | DomainDiagnostic:
    """Validate dependent bounds and return entries plus prerequisite-first order."""
    indices = frozenset(bounds)
    entries: dict[str, OutputDomain] = {}
    for index in lhs_order:
        lower, upper = bounds[index]
        lower_path = f"equations[{equation_position}].domains.{index}.lower"
        upper_path = f"equations[{equation_position}].domains.{index}.upper"
        dependencies: set[str] = set()
        for expression, path in ((lower, lower_path), (upper, upper_path)):
            references = free_symbols(expression) & indices
            if index in references:
                return DomainDiagnostic(
                    f"output domain {index} cannot depend on itself", path
                )
            form = affine_form(expression) if references else None
            if references and form is None:
                return DomainDiagnostic(
                    "dependent output-domain bound must use the affine-integer grammar", path
                )
            if form is not None:
                noninteger = set(form[0]) - indices - declared_integer_symbols
                if noninteger:
                    return DomainDiagnostic(
                        "dependent output-domain bound references non-integer variables: "
                        + ", ".join(sorted(noninteger)),
                        path,
                    )
            dependencies.update(references)
        entries[index] = OutputDomain(
            index, lower, upper, lower_path, upper_path, frozenset(dependencies)
        )

    completed: set[str] = set()
    order: list[str] = []
    while len(order) < len(lhs_order):
        eligible = [
            index
            for index in lhs_order
            if index not in completed and entries[index].dependencies <= completed
        ]
        if not eligible:
            return DomainDiagnostic(
                "output-domain dependencies contain a cycle",
                f"equations[{equation_position}].domains",
            )
        chosen = eligible[0]
        completed.add(chosen)
        order.append(chosen)
    return tuple(entries[index] for index in lhs_order), tuple(order)


def free_symbols(expression: Expression, bound: frozenset[str] = frozenset()) -> set[str]:
    from py_science.formula.expressions import Sum

    if isinstance(expression, Symbol):
        return set() if expression.name in bound else {expression.name}
    if isinstance(expression, Sum):
        result = free_symbols(expression.lower, bound) | free_symbols(expression.upper, bound)
        return result | free_symbols(expression.body, bound | {expression.index})
    result: set[str] = set()
    for child in expression_children(expression):
        result.update(free_symbols(child, bound))
    return result


def affine_form(expression: Expression) -> tuple[dict[str, Fraction], Fraction] | None:
    """Parse the ADR affine grammar without asking SymPy to define acceptance."""
    if isinstance(expression, IntegerLiteral):
        return {}, Fraction(expression.value)
    if isinstance(expression, RationalLiteral):
        # Dependent bounds are affine-*integer*: rational literals are admitted only
        # when they denote an integer.
        value = Fraction(expression.numerator, expression.positive_denominator)
        return ({}, value) if value.denominator == 1 else None
    if isinstance(expression, Symbol):
        return {expression.name: Fraction(1)}, Fraction(0)
    if not isinstance(expression, BinaryExpression):
        return None
    if expression.operator in {BinaryOperator.ADD, BinaryOperator.SUBTRACT}:
        left, right = affine_form(expression.left), affine_form(expression.right)
        if left is None or right is None:
            return None
        sign = Fraction(1) if expression.operator is BinaryOperator.ADD else Fraction(-1)
        coefficients = dict(left[0])
        for name, coefficient in right[0].items():
            coefficients[name] = coefficients.get(name, Fraction(0)) + sign * coefficient
            if coefficients[name] == 0:
                del coefficients[name]
        return coefficients, left[1] + sign * right[1]
    if expression.operator is BinaryOperator.MULTIPLY:
        left, right = affine_form(expression.left), affine_form(expression.right)
        if left is None or right is None:
            return None
        if left[0] and right[0]:
            return None
        scalar, affine = (left[1], right) if not left[0] else (right[1], left)
        if scalar.denominator != 1:
            return None
        return ({name: scalar * value for name, value in affine[0].items()}, scalar * affine[1])
    return None


def extent(
    domain: OutputDomain,
    predecessors: dict[str, OutputDomain],
    reasoner: AffineReasoner,
) -> tuple[Expression, bool, tuple[RelationshipUse, ...]]:
    """Return inclusive extent and bounded evidence that it is nonnegative."""
    value = _add(_subtract(domain.upper, domain.lower), IntegerLiteral(1))
    reduced = _minimum_from_predecessor_bounds(value, predecessors, set())
    proved, uses = reasoner.prove_nonnegative(reduced)
    return value, proved, uses


def _minimum_from_predecessor_bounds(
    expression: Expression,
    predecessors: dict[str, OutputDomain],
    visiting: set[str],
) -> Expression:
    form = affine_form(expression)
    if form is None:
        return expression
    result: Expression = _fraction_expression(form[1])
    for name, coefficient in form[0].items():
        domain = predecessors.get(name)
        if domain is None or name in visiting:
            term = Symbol(name)
        else:
            endpoint = domain.lower if coefficient >= 0 else domain.upper
            term = _minimum_from_predecessor_bounds(endpoint, predecessors, visiting | {name})
        scaled = _multiply(_fraction_expression(coefficient), term)
        result = _add(result, scaled)
    return result


def _fraction_expression(value: Fraction) -> Expression:
    if value.denominator == 1:
        return IntegerLiteral(value.numerator)
    return RationalLiteral(value.numerator, value.denominator)


def _add(left: Expression, right: Expression) -> Expression:
    return BinaryExpression(BinaryOperator.ADD, left, right)


def _subtract(left: Expression, right: Expression) -> Expression:
    return BinaryExpression(BinaryOperator.SUBTRACT, left, right)


def _multiply(left: Expression, right: Expression) -> Expression:
    return BinaryExpression(BinaryOperator.MULTIPLY, left, right)
