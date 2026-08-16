# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportIndexIssue=false, reportUnusedImport=false
from __future__ import annotations

from dataclasses import dataclass

from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    IndexedValue,
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
            self.additions + other.additions,
            self.subtractions + other.subtractions,
            self.multiplications + other.multiplications,
            self.divisions + other.divisions,
            self.powers + other.powers,
        )


def count_operations(expression: Expression) -> OperationTally:
    if isinstance(expression, BinaryExpression):
        base = count_operations(expression.left).combine(count_operations(expression.right))
        return base.combine(
            {
                BinaryOperator.ADD: OperationTally(additions=1),
                BinaryOperator.SUBTRACT: OperationTally(subtractions=1),
                BinaryOperator.MULTIPLY: OperationTally(multiplications=1),
                BinaryOperator.DIVIDE: OperationTally(divisions=1),
                BinaryOperator.POWER: OperationTally(powers=1),
            }[expression.operator]
        )
    if isinstance(expression, (Call, IndexedValue)):
        return _combine(
            expression.arguments if isinstance(expression, Call) else expression.indices
        )
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
