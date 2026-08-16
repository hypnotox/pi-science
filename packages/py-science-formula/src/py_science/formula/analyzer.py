from __future__ import annotations

from dataclasses import dataclass

from py_science.formula.expressions import BinaryExpression, BinaryOperator, Expression


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
            self.additions
            + self.subtractions
            + self.multiplications
            + self.divisions
            + self.powers
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
    if not isinstance(expression, BinaryExpression):
        return OperationTally()

    children = count_operations(expression.left).combine(count_operations(expression.right))
    match expression.operator:
        case BinaryOperator.ADD:
            operation = OperationTally(additions=1)
        case BinaryOperator.SUBTRACT:
            operation = OperationTally(subtractions=1)
        case BinaryOperator.MULTIPLY:
            operation = OperationTally(multiplications=1)
        case BinaryOperator.DIVIDE:
            operation = OperationTally(divisions=1)
        case BinaryOperator.POWER:
            operation = OperationTally(powers=1)
    return children.combine(operation)
