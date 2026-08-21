from __future__ import annotations

from dataclasses import dataclass

from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    IndexedValue,
    Let,
    Sum,
)


@dataclass(frozen=True, slots=True)
class OperationTally:
    additions: int = 0
    subtractions: int = 0
    multiplications: int = 0
    divisions: int = 0
    powers: int = 0

    @property
    def total(self) -> int:
        return (
            self.additions + self.subtractions + self.multiplications + self.divisions + self.powers
        )

    def combine(self, other: OperationTally) -> OperationTally:
        return OperationTally(
            additions=self.additions + other.additions,
            subtractions=self.subtractions + other.subtractions,
            multiplications=self.multiplications + other.multiplications,
            divisions=self.divisions + other.divisions,
            powers=self.powers + other.powers,
        )


def count_operations(expression: Expression) -> OperationTally:
    if isinstance(expression, BinaryExpression):
        children = count_operations(expression.left).combine(count_operations(expression.right))
        operation = {
            BinaryOperator.ADD: OperationTally(additions=1),
            BinaryOperator.SUBTRACT: OperationTally(subtractions=1),
            BinaryOperator.MULTIPLY: OperationTally(multiplications=1),
            BinaryOperator.DIVIDE: OperationTally(divisions=1),
            BinaryOperator.POWER: OperationTally(powers=1),
        }[expression.operator]
        return children.combine(operation)
    if isinstance(expression, Call):
        return _combine(expression.arguments)
    if isinstance(expression, IndexedValue):
        return _combine(expression.indices)
    if isinstance(expression, Let):
        return count_operations(expression.value).combine(count_operations(expression.body))
    if isinstance(expression, Sum):
        return (
            count_operations(expression.body)
            .combine(count_operations(expression.lower))
            .combine(count_operations(expression.upper))
        )
    return OperationTally()


def _combine(expressions: tuple[Expression, ...]) -> OperationTally:
    tally = OperationTally()
    for expression in expressions:
        tally = tally.combine(count_operations(expression))
    return tally
