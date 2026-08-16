from __future__ import annotations

from dataclasses import dataclass, field

from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    IndexedValue,
    IntegerLiteral,
    Sum,
    Symbol,
    substitute,
)
from py_science.formula.models import MathematicalDomain, SymbolicOperationCounts
from py_science.formula.sympy_backend import render

_ZERO = IntegerLiteral(0)
_ONE = IntegerLiteral(1)


@dataclass(frozen=True, slots=True)
class FunctionRule:
    name: str
    parameters: tuple[str, ...]
    body: Expression


@dataclass(frozen=True, slots=True)
class PrimitiveRule:
    name: str
    parameters: tuple[str, ...]
    work: Expression


@dataclass(frozen=True, slots=True)
class WorkContext:
    definitions: dict[str, FunctionRule]
    primitives: dict[str, PrimitiveRule]
    variable_domains: dict[str, MathematicalDomain]
    integer_symbols: frozenset[str] = frozenset()
    call_stack: tuple[str, ...] = ()

    def with_integer_symbol(self, name: str) -> WorkContext:
        return WorkContext(
            definitions=self.definitions,
            primitives=self.primitives,
            variable_domains=self.variable_domains,
            integer_symbols=self.integer_symbols | {name},
            call_stack=self.call_stack,
        )

    def for_call(
        self,
        name: str,
        extra_integer_symbols: frozenset[str],
    ) -> WorkContext:
        return WorkContext(
            definitions=self.definitions,
            primitives=self.primitives,
            variable_domains=self.variable_domains,
            integer_symbols=self.integer_symbols | extra_integer_symbols,
            call_stack=(*self.call_stack, name),
        )


@dataclass(frozen=True, slots=True)
class SymbolicTally:
    additions: Expression = _ZERO
    subtractions: Expression = _ZERO
    multiplications: Expression = _ZERO
    divisions: Expression = _ZERO
    powers: Expression = _ZERO

    def combine(self, other: SymbolicTally) -> SymbolicTally:
        return SymbolicTally(
            additions=_add(self.additions, other.additions),
            subtractions=_add(self.subtractions, other.subtractions),
            multiplications=_add(self.multiplications, other.multiplications),
            divisions=_add(self.divisions, other.divisions),
            powers=_add(self.powers, other.powers),
        )

    def scale(self, factor: Expression) -> SymbolicTally:
        return SymbolicTally(
            additions=_multiply(self.additions, factor),
            subtractions=_multiply(self.subtractions, factor),
            multiplications=_multiply(self.multiplications, factor),
            divisions=_multiply(self.divisions, factor),
            powers=_multiply(self.powers, factor),
        )

    @property
    def total(self) -> Expression:
        result = _ZERO
        for value in (
            self.additions,
            self.subtractions,
            self.multiplications,
            self.divisions,
            self.powers,
        ):
            result = _add(result, value)
        return result


def _empty_invocations() -> dict[str, Expression]:
    return {}


def _empty_strings() -> set[str]:
    return set()


@dataclass(slots=True)
class WorkAnalysis:
    operations: SymbolicTally = field(default_factory=SymbolicTally)
    opaque_work: Expression = _ZERO
    invocations: dict[str, Expression] = field(default_factory=_empty_invocations)
    unknown_costs: set[str] = field(default_factory=_empty_strings)
    unresolved: set[str] = field(default_factory=_empty_strings)

    def combine(self, other: WorkAnalysis) -> WorkAnalysis:
        invocations = dict(self.invocations)
        for name, count in other.invocations.items():
            invocations[name] = _add(invocations.get(name, _ZERO), count)
        return WorkAnalysis(
            operations=self.operations.combine(other.operations),
            opaque_work=_add(self.opaque_work, other.opaque_work),
            invocations=invocations,
            unknown_costs=self.unknown_costs | other.unknown_costs,
            unresolved=self.unresolved | other.unresolved,
        )

    def scale(self, factor: Expression) -> WorkAnalysis:
        return WorkAnalysis(
            operations=self.operations.scale(factor),
            opaque_work=_multiply(self.opaque_work, factor),
            invocations={
                name: _multiply(count, factor) for name, count in self.invocations.items()
            },
            unknown_costs=set(self.unknown_costs),
            unresolved=set(self.unresolved),
        )

    @property
    def total_work(self) -> Expression:
        return _add(self.operations.total, self.opaque_work)


def analyze_work(expression: Expression, context: WorkContext) -> WorkAnalysis:
    if isinstance(expression, BinaryExpression):
        children = analyze_work(expression.left, context).combine(
            analyze_work(expression.right, context)
        )
        operation = {
            BinaryOperator.ADD: SymbolicTally(additions=_ONE),
            BinaryOperator.SUBTRACT: SymbolicTally(subtractions=_ONE),
            BinaryOperator.MULTIPLY: SymbolicTally(multiplications=_ONE),
            BinaryOperator.DIVIDE: SymbolicTally(divisions=_ONE),
            BinaryOperator.POWER: SymbolicTally(powers=_ONE),
        }[expression.operator]
        return children.combine(WorkAnalysis(operations=operation))
    if isinstance(expression, Call):
        return _analyze_call(expression, context)
    if isinstance(expression, Sum):
        return _analyze_sum(expression, context)
    if isinstance(expression, IndexedValue):
        # Indexing and index-expression evaluation are outside mathematical work.
        return WorkAnalysis()
    return WorkAnalysis()


def cardinality(
    lower: Expression,
    upper: Expression,
    context: WorkContext,
    label: str,
) -> tuple[Expression, str | None]:
    if isinstance(lower, IntegerLiteral) and isinstance(upper, IntegerLiteral):
        return IntegerLiteral(max(upper.value - lower.value + 1, 0)), None
    if is_integer_expression(lower, context) and is_integer_expression(upper, context):
        extent = _add(_subtract(upper, lower), _ONE)
        return Call("Max", (extent, _ZERO)), None
    return (
        Call("cardinality", (lower, upper)),
        f"{label} cardinality requires integral bounds",
    )


def is_integer_expression(expression: Expression, context: WorkContext) -> bool:
    if isinstance(expression, IntegerLiteral):
        return True
    if isinstance(expression, Symbol):
        declaration = context.variable_domains.get(expression.name)
        return expression.name in context.integer_symbols or (
            declaration is not None and declaration.is_integer
        )
    if isinstance(expression, IndexedValue):
        declaration = context.variable_domains.get(expression.name)
        return declaration is not None and declaration.is_integer
    if isinstance(expression, BinaryExpression):
        if expression.operator in {
            BinaryOperator.ADD,
            BinaryOperator.SUBTRACT,
            BinaryOperator.MULTIPLY,
        }:
            return is_integer_expression(expression.left, context) and is_integer_expression(
                expression.right, context
            )
        if expression.operator is BinaryOperator.POWER:
            return (
                is_integer_expression(expression.left, context)
                and isinstance(expression.right, IntegerLiteral)
                and expression.right.value >= 0
            )
        return False
    if isinstance(expression, Call):
        definition = context.definitions.get(expression.name)
        if definition is None or len(definition.parameters) != len(expression.arguments):
            return False
        replacements = dict(zip(definition.parameters, expression.arguments, strict=True))
        return is_integer_expression(substitute(definition.body, replacements), context)
    return is_integer_expression(expression.body, context.with_integer_symbol(expression.index))


def render_work(expression: Expression) -> str:
    return render(expression).sympy


def render_operations(tally: SymbolicTally) -> SymbolicOperationCounts:
    return SymbolicOperationCounts(
        additions=render_work(tally.additions),
        subtractions=render_work(tally.subtractions),
        multiplications=render_work(tally.multiplications),
        divisions=render_work(tally.divisions),
        powers=render_work(tally.powers),
    )


def render_invocations(invocations: dict[str, Expression]) -> dict[str, str]:
    return {name: render_work(count) for name, count in sorted(invocations.items())}


def substitute_analysis(
    analysis: WorkAnalysis,
    replacements: dict[str, Expression],
) -> WorkAnalysis:
    return WorkAnalysis(
        operations=SymbolicTally(
            additions=substitute(analysis.operations.additions, replacements),
            subtractions=substitute(analysis.operations.subtractions, replacements),
            multiplications=substitute(analysis.operations.multiplications, replacements),
            divisions=substitute(analysis.operations.divisions, replacements),
            powers=substitute(analysis.operations.powers, replacements),
        ),
        opaque_work=substitute(analysis.opaque_work, replacements),
        invocations={
            name: substitute(count, replacements) for name, count in analysis.invocations.items()
        },
        unknown_costs=set(analysis.unknown_costs),
        unresolved=set(analysis.unresolved),
    )


def _analyze_sum(expression: Sum, context: WorkContext) -> WorkAnalysis:
    scoped = context.with_integer_symbol(expression.index)
    body = analyze_work(expression.body, scoped)
    count, unresolved = cardinality(
        expression.lower,
        expression.upper,
        context,
        f"sum index {expression.index}",
    )
    result = body.scale(count)
    reduction = _max_zero(_subtract(count, _ONE))
    result.operations = result.operations.combine(SymbolicTally(additions=reduction))
    if unresolved is not None:
        result.unresolved.add(unresolved)
    return result


def _analyze_call(expression: Call, context: WorkContext) -> WorkAnalysis:
    result = WorkAnalysis()
    for argument in expression.arguments:
        result = result.combine(analyze_work(argument, context))
    definition = context.definitions.get(expression.name)
    if definition is not None:
        if expression.name in context.call_stack:
            result.unresolved.add(f"recursive function definition for {expression.name}")
            return result
        placeholder_symbols: dict[str, Symbol] = {
            parameter: Symbol(f"__arg_{expression.name}_{index}")
            for index, parameter in enumerate(definition.parameters)
        }
        placeholders: dict[str, Expression] = dict(placeholder_symbols)
        reverse: dict[str, Expression] = {
            placeholder.name: argument
            for placeholder, argument in zip(
                placeholder_symbols.values(), expression.arguments, strict=True
            )
        }
        integer_placeholders: frozenset[str] = frozenset(
            placeholder.name
            for placeholder, argument in zip(
                placeholder_symbols.values(), expression.arguments, strict=True
            )
            if is_integer_expression(argument, context)
        )
        internal = substitute(definition.body, placeholders)
        body = analyze_work(
            internal,
            context.for_call(expression.name, integer_placeholders),
        )
        return result.combine(substitute_analysis(body, reverse))

    primitive = context.primitives.get(expression.name)
    if primitive is not None:
        result.invocations[expression.name] = _add(
            result.invocations.get(expression.name, _ZERO),
            _ONE,
        )
        replacements = dict(zip(primitive.parameters, expression.arguments, strict=True))
        result.opaque_work = _add(
            result.opaque_work,
            substitute(primitive.work, replacements),
        )
        return result

    unknown_name = f"C_{expression.name}"
    result.unknown_costs.add(unknown_name)
    result.unresolved.add(f"unknown cost for {expression.name}")
    result.opaque_work = _add(
        result.opaque_work,
        Call(unknown_name, expression.arguments),
    )
    return result


def _add(left: Expression, right: Expression) -> Expression:
    if _is_zero(left):
        return right
    if _is_zero(right):
        return left
    if isinstance(left, IntegerLiteral) and isinstance(right, IntegerLiteral):
        return IntegerLiteral(left.value + right.value)
    return BinaryExpression(BinaryOperator.ADD, left, right)


def _subtract(left: Expression, right: Expression) -> Expression:
    if _is_zero(right):
        return left
    if isinstance(left, IntegerLiteral) and isinstance(right, IntegerLiteral):
        return IntegerLiteral(left.value - right.value)
    return BinaryExpression(BinaryOperator.SUBTRACT, left, right)


def _multiply(left: Expression, right: Expression) -> Expression:
    if _is_zero(left) or _is_zero(right):
        return _ZERO
    if _is_one(left):
        return right
    if _is_one(right):
        return left
    if isinstance(left, IntegerLiteral) and isinstance(right, IntegerLiteral):
        return IntegerLiteral(left.value * right.value)
    return BinaryExpression(BinaryOperator.MULTIPLY, left, right)


def _max_zero(expression: Expression) -> Expression:
    if isinstance(expression, IntegerLiteral):
        return IntegerLiteral(max(expression.value, 0))
    return Call("Max", (expression, _ZERO))


def _is_zero(expression: Expression) -> bool:
    return isinstance(expression, IntegerLiteral) and expression.value == 0


def _is_one(expression: Expression) -> bool:
    return isinstance(expression, IntegerLiteral) and expression.value == 1
