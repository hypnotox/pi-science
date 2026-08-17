from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from py_science.formula.exact_values import ExactRational


class RelationshipOperator(StrEnum):
    EQUAL = "equal"
    LESS = "less"
    LESS_EQUAL = "less_equal"
    GREATER = "greater"
    GREATER_EQUAL = "greater_equal"


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
class RationalLiteral:
    numerator: int
    positive_denominator: int

    def __post_init__(self) -> None:
        canonical = ExactRational(self.numerator, self.positive_denominator)
        object.__setattr__(self, "numerator", canonical.numerator)
        object.__setattr__(self, "positive_denominator", canonical.denominator)


@dataclass(frozen=True, slots=True)
class InfinityLiteral:
    sign: int

    def __post_init__(self) -> None:
        if self.sign not in {-1, 1}:
            raise ValueError("infinity sign must be -1 or 1")


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


@dataclass(frozen=True, slots=True)
class Relationship:
    operator: RelationshipOperator
    left: Expression
    right: Expression


type Expression = IntegerLiteral | RationalLiteral | InfinityLiteral | Symbol | IndexedValue | Call | Sum | BinaryExpression  # noqa: E501
type Formula = Expression | Equation | Relationship


def exact_integer_value(expression: Expression) -> int | None:
    if isinstance(expression, IntegerLiteral):
        return expression.value
    if isinstance(expression, RationalLiteral) and expression.positive_denominator == 1:
        return expression.numerator
    return None


def expression_children(expression: Expression) -> tuple[Expression, ...]:
    if isinstance(expression, BinaryExpression):
        return (expression.left, expression.right)
    if isinstance(expression, IndexedValue):
        return expression.indices
    if isinstance(expression, Call):
        return expression.arguments
    if isinstance(expression, Sum):
        return (expression.lower, expression.upper, expression.body)
    return ()


def expression_node_count(expression: Expression) -> int:
    return 1 + sum(expression_node_count(child) for child in expression_children(expression))


class ExpressionTooComplex(RuntimeError):
    pass


def substitute(
    expression: Expression,
    replacements: dict[str, Expression],
    *,
    max_nodes: int | None = None,
) -> Expression:
    """Substitute without constructing an expansion that exceeds ``max_nodes``."""
    remaining = max_nodes

    def visit(value: Expression, scoped: dict[str, Expression]) -> Expression:
        nonlocal remaining
        if isinstance(value, Symbol) and value.name in scoped:
            replacement = scoped[value.name]
            _consume(expression_node_count(replacement))
            return replacement
        _consume(1)
        if isinstance(value, IndexedValue):
            return IndexedValue(value.name, tuple(visit(index, scoped) for index in value.indices))
        if isinstance(value, Call):
            return Call(value.name, tuple(visit(argument, scoped) for argument in value.arguments))
        if isinstance(value, Sum):
            inner = {name: item for name, item in scoped.items() if name != value.index}
            return Sum(
                visit(value.body, inner),
                value.index,
                visit(value.lower, scoped),
                visit(value.upper, scoped),
            )
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator,
                visit(value.left, scoped),
                visit(value.right, scoped),
            )
        return value

    def _consume(nodes: int) -> None:
        nonlocal remaining
        if remaining is None:
            return
        remaining -= nodes
        if remaining < 0:
            raise ExpressionTooComplex("substitution-expanded work exceeds its structural bound")

    return visit(expression, replacements)
