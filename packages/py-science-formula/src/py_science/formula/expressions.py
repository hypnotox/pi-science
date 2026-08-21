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
class Let:
    """A bounded nonrecursive lexical binding.

    ``value`` is evaluated in the enclosing scope; ``name`` is visible only in
    ``body``.  It is deliberately not a generic callable expression.
    """

    name: str
    value: Expression
    body: Expression


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


type Expression = (
    IntegerLiteral
    | RationalLiteral
    | InfinityLiteral
    | Symbol
    | IndexedValue
    | Call
    | Sum
    | Let
    | BinaryExpression
)
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
    if isinstance(expression, Let):
        return (expression.value, expression.body)
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

    def visit(
        value: Expression,
        scoped: dict[str, Expression],
        enclosing_binders: frozenset[str],
    ) -> Expression:
        nonlocal remaining
        if isinstance(value, Symbol) and value.name in scoped:
            replacement = scoped[value.name]
            _consume(expression_node_count(replacement))
            return replacement
        _consume(1)
        if isinstance(value, IndexedValue):
            return IndexedValue(
                value.name,
                tuple(visit(index, scoped, enclosing_binders) for index in value.indices),
            )
        if isinstance(value, Call):
            return Call(
                value.name,
                tuple(visit(argument, scoped, enclosing_binders) for argument in value.arguments),
            )
        if isinstance(value, Sum):
            inner = {name: item for name, item in scoped.items() if name != value.index}
            index = value.index
            body = value.body
            introduced: set[str] = set()
            for item in inner.values():
                introduced.update(_free_names(item))
            # A replacement introduced into the body must not become captured
            # by this aggregate's binder.
            if index in introduced:
                index = _fresh_name(index, body, inner, enclosing_binders)
                body = _rename_bound(body, value.index, index)
            return Sum(
                visit(body, inner, enclosing_binders | {index}),
                index,
                visit(value.lower, scoped, enclosing_binders),
                visit(value.upper, scoped, enclosing_binders),
            )
        if isinstance(value, Let):
            # The binding is nonrecursive: its value sees the enclosing
            # replacement scope while its body hides its own name.  Rename the
            # binder before substituting when a replacement would otherwise be
            # captured in the body.
            inner = {name: item for name, item in scoped.items() if name != value.name}
            name = value.name
            body = value.body
            introduced: set[str] = set()
            for item in inner.values():
                introduced.update(_free_names(item))
            if name in introduced:
                name = _fresh_name(name, body, inner, enclosing_binders)
                body = _rename_bound(body, value.name, name)
            return Let(
                name,
                visit(value.value, scoped, enclosing_binders),
                visit(body, inner, enclosing_binders | {name}),
            )
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator,
                visit(value.left, scoped, enclosing_binders),
                visit(value.right, scoped, enclosing_binders),
            )
        return value

    def _consume(nodes: int) -> None:
        nonlocal remaining
        if remaining is None:
            return
        remaining -= nodes
        if remaining < 0:
            raise ExpressionTooComplex("substitution-expanded work exceeds its structural bound")

    return visit(expression, replacements, frozenset())


def lower_let_bindings(
    expression: Expression,
    *,
    max_nodes: int = 4_096,
) -> Expression:
    """Lower lexical bindings only at a represented-value consumer boundary."""

    def visit(value: Expression) -> Expression:
        if isinstance(value, IndexedValue):
            result: Expression = IndexedValue(
                value.name,
                tuple(visit(item) for item in value.indices),
            )
        elif isinstance(value, Call):
            result = Call(value.name, tuple(visit(item) for item in value.arguments))
        elif isinstance(value, Sum):
            result = Sum(visit(value.body), value.index, visit(value.lower), visit(value.upper))
        elif isinstance(value, Let):
            lowered_value = visit(value.value)
            lowered_body = visit(value.body)
            result = substitute(
                lowered_body,
                {value.name: lowered_value},
                max_nodes=max_nodes,
            )
        elif isinstance(value, BinaryExpression):
            result = BinaryExpression(value.operator, visit(value.left), visit(value.right))
        else:
            result = value
        if expression_node_count(result) > max_nodes:
            raise ExpressionTooComplex("lexical binding expansion exceeds its structural bound")
        return result

    return visit(expression)


def _free_names(value: Expression, bound: frozenset[str] = frozenset()) -> set[str]:
    if isinstance(value, Symbol):
        return set() if value.name in bound else {value.name}
    if isinstance(value, Sum):
        return (
            _free_names(value.lower, bound)
            | _free_names(value.upper, bound)
            | _free_names(value.body, bound | {value.index})
        )
    if isinstance(value, Let):
        return _free_names(value.value, bound) | _free_names(value.body, bound | {value.name})
    result: set[str] = set()
    for child in expression_children(value):
        result.update(_free_names(child, bound))
    return result


def _fresh_name(
    base: str,
    body: Expression,
    replacements: dict[str, Expression],
    reserved: frozenset[str] = frozenset(),
) -> str:
    occupied = _all_names(body) | set(replacements) | set(reserved)
    for item in replacements.values():
        occupied.update(_all_names(item))
    candidate = f"{base}_let"
    suffix = 1
    while candidate in occupied:
        suffix += 1
        candidate = f"{base}_let_{suffix}"
    return candidate


def _all_names(value: Expression) -> set[str]:
    result: set[str] = set()
    if isinstance(value, (Symbol, IndexedValue, Call)):
        result.add(value.name)
    if isinstance(value, Sum):
        result.add(value.index)
    if isinstance(value, Let):
        result.add(value.name)
    for child in expression_children(value):
        result.update(_all_names(child))
    return result


def _rename_bound(value: Expression, old: str, new: str) -> Expression:
    if isinstance(value, Symbol):
        return Symbol(new) if value.name == old else value
    if isinstance(value, IndexedValue):
        return IndexedValue(
            value.name, tuple(_rename_bound(item, old, new) for item in value.indices)
        )
    if isinstance(value, Call):
        return Call(value.name, tuple(_rename_bound(item, old, new) for item in value.arguments))
    if isinstance(value, Sum):
        body = value.body if value.index == old else _rename_bound(value.body, old, new)
        return Sum(
            body,
            value.index,
            _rename_bound(value.lower, old, new),
            _rename_bound(value.upper, old, new),
        )
    if isinstance(value, Let):
        body = value.body if value.name == old else _rename_bound(value.body, old, new)
        return Let(value.name, _rename_bound(value.value, old, new), body)
    if isinstance(value, BinaryExpression):
        return BinaryExpression(
            value.operator,
            _rename_bound(value.left, old, new),
            _rename_bound(value.right, old, new),
        )
    return value
