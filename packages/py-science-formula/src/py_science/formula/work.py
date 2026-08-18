from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
    Sum,
    Symbol,
    exact_integer_value,
    expression_children,
    expression_node_count,
    substitute,
)
from py_science.formula.models import MathematicalDomain, SymbolicOperationCounts
from py_science.formula.sympy_backend import render

_ZERO = IntegerLiteral(0)
_ONE = IntegerLiteral(1)
# This is deliberately below the request-wide parsed-node limit: derived work is
# rendered and reported repeatedly, so it needs its own pre-SymPy bound.
MAX_WORK_NODES = 4_096
MAX_WORK_RENDER_BYTES = 196_608
_INFINITY_WORK_BLOCKER = "mathematical infinity has no finite direct-evaluation work"


@dataclass(slots=True)
class WorkRenderBudget:
    bytes: int = 0

    def accept(self, expression: Expression) -> None:
        estimate = _rendered_size_upper_bound(expression)
        if self.bytes + estimate > MAX_WORK_RENDER_BYTES:
            raise ExpressionTooComplex("aggregate work rendering exceeds its size bound")
        self.bytes += estimate


@dataclass(frozen=True, slots=True)
class FunctionRule:
    name: str
    parameters: tuple[str, ...]
    body: Expression
    source: str


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
    direct_work_blockers: set[str] = field(default_factory=_empty_strings)

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
            direct_work_blockers=self.direct_work_blockers | other.direct_work_blockers,
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
            direct_work_blockers=set(self.direct_work_blockers),
        )

    @property
    def total_work(self) -> Expression:
        return _add(self.operations.total, self.opaque_work)


def analyze_work(expression: Expression, context: WorkContext) -> WorkAnalysis:
    if isinstance(expression, InfinityLiteral):
        return WorkAnalysis(direct_work_blockers={_INFINITY_WORK_BLOCKER})
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
        # Indexing and index-expression evaluation are outside mathematical work,
        # but infinity in an index still prevents finite direct evaluation.
        blockers = {
            blocker
            for index in expression.indices
            for blocker in analyze_work(index, context).direct_work_blockers
        }
        return WorkAnalysis(direct_work_blockers=blockers)
    return WorkAnalysis()


def cardinality(
    lower: Expression,
    upper: Expression,
    context: WorkContext,
    label: str,
) -> tuple[Expression, str | None]:
    if _contains_infinity(lower) or _contains_infinity(upper):
        return IntegerLiteral(0), "infinite iterator has no finite direct-evaluation work"
    lower_value = exact_integer_value(lower)
    upper_value = exact_integer_value(upper)
    if lower_value is not None and upper_value is not None:
        return IntegerLiteral(max(upper_value - lower_value + 1, 0)), None
    extent_value = _zero_to_nonnegative_extent(lower, upper, context)
    if extent_value is not None:
        return extent_value, None
    if is_integer_expression(lower, context) and is_integer_expression(upper, context):
        extent = _add(_subtract(upper, lower), _ONE)
        return Call("Max", (extent, _ZERO)), None
    return (
        Call("cardinality", (lower, upper)),
        f"{label} cardinality requires integral bounds",
    )


def _contains_infinity(expression: Expression) -> bool:
    return isinstance(expression, InfinityLiteral) or any(
        _contains_infinity(child) for child in expression_children(expression)
    )


def _zero_to_nonnegative_extent(
    lower: Expression, upper: Expression, context: WorkContext
) -> Expression | None:
    if not _is_zero(lower) or not isinstance(upper, BinaryExpression):
        return None
    if upper.operator is not BinaryOperator.SUBTRACT or not _is_one(upper.right):
        return None
    extent = upper.left
    if not is_integer_expression(extent, context) or not is_nonnegative_expression(extent, context):
        return None
    return extent


def is_nonnegative_expression(expression: Expression, context: WorkContext) -> bool:
    if isinstance(expression, IntegerLiteral):
        return expression.value >= 0
    if isinstance(expression, RationalLiteral):
        return expression.numerator >= 0
    if isinstance(expression, (Symbol, IndexedValue)):
        declaration = context.variable_domains.get(expression.name)
        return declaration in {
            MathematicalDomain.NONNEGATIVE_INTEGER,
            MathematicalDomain.NONNEGATIVE_REAL,
            MathematicalDomain.POSITIVE_INTEGER,
            MathematicalDomain.POSITIVE_REAL,
        }
    if isinstance(expression, Call):
        definition = context.definitions.get(expression.name)
        if definition is None or len(definition.parameters) != len(expression.arguments):
            return False
        replacements = dict(zip(definition.parameters, expression.arguments, strict=True))
        return is_nonnegative_expression(
            substitute(definition.body, replacements, max_nodes=MAX_WORK_NODES), context
        )
    if isinstance(expression, BinaryExpression):
        if expression.operator in {BinaryOperator.ADD, BinaryOperator.MULTIPLY}:
            return is_nonnegative_expression(
                expression.left, context
            ) and is_nonnegative_expression(expression.right, context)
        if expression.operator is BinaryOperator.POWER:
            exponent = exact_integer_value(expression.right)
            return exponent is not None and exponent >= 0 and (
                exponent % 2 == 0
                or is_nonnegative_expression(expression.left, context)
            )
    return False


def is_positive_expression(expression: Expression, context: WorkContext) -> bool:
    if isinstance(expression, IntegerLiteral):
        return expression.value > 0
    if isinstance(expression, RationalLiteral):
        return expression.numerator > 0
    if isinstance(expression, (Symbol, IndexedValue)):
        return context.variable_domains.get(expression.name) in {
            MathematicalDomain.POSITIVE_INTEGER,
            MathematicalDomain.POSITIVE_REAL,
        }
    if isinstance(expression, Call):
        definition = context.definitions.get(expression.name)
        if definition is None or len(definition.parameters) != len(expression.arguments):
            return False
        replacements = dict(zip(definition.parameters, expression.arguments, strict=True))
        return is_positive_expression(
            substitute(definition.body, replacements, max_nodes=MAX_WORK_NODES), context
        )
    if isinstance(expression, BinaryExpression) and expression.operator is BinaryOperator.MULTIPLY:
        return is_positive_expression(expression.left, context) and is_positive_expression(
            expression.right, context
        )
    if (
        isinstance(expression, BinaryExpression)
        and expression.operator is BinaryOperator.POWER
    ):
        exponent = exact_integer_value(expression.right)
        return exponent is not None and exponent > 0 and is_positive_expression(
            expression.left, context
        )
    return False


def is_integer_expression(expression: Expression, context: WorkContext) -> bool:
    if isinstance(expression, IntegerLiteral):
        return True
    if isinstance(expression, RationalLiteral):
        return expression.positive_denominator == 1
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
            exponent = exact_integer_value(expression.right)
            return (
                is_integer_expression(expression.left, context)
                and exponent is not None
                and exponent >= 0
            )
        return False
    if isinstance(expression, Call):
        definition = context.definitions.get(expression.name)
        if definition is None or len(definition.parameters) != len(expression.arguments):
            return False
        replacements = dict(zip(definition.parameters, expression.arguments, strict=True))
        return is_integer_expression(
            substitute(definition.body, replacements, max_nodes=MAX_WORK_NODES), context
        )
    if isinstance(expression, Sum):
        return is_integer_expression(expression.body, context.with_integer_symbol(expression.index))
    return False


def render_work(expression: Expression, budget: WorkRenderBudget) -> str:
    # Do not hand a substitution-expanded tree to SymPy before bounding it.
    if expression_node_count(expression) > MAX_WORK_NODES:
        raise ExpressionTooComplex("aggregate work exceeds its structural bound")
    budget.accept(expression)
    return render(expression).sympy


def _rendered_size_upper_bound(expression: Expression) -> int:
    """A cheap conservative IR spelling bound, evaluated before SymPy rendering."""
    if isinstance(expression, RationalLiteral):
        return len(str(expression.numerator)) + len(str(expression.positive_denominator)) + 1
    if isinstance(expression, InfinityLiteral):
        return 3
    if isinstance(expression, IntegerLiteral):
        # log10(2) is below 0.31; include a possible leading minus sign.
        digits = max(1, (expression.value.bit_length() * 31 + 99) // 100)
        return digits + int(expression.value < 0)
    if isinstance(expression, Symbol):
        return len(expression.name)
    if isinstance(expression, IndexedValue):
        return (
            len(expression.name)
            + 2
            + sum(_rendered_size_upper_bound(index) + 1 for index in expression.indices)
        )
    if isinstance(expression, Call):
        return (
            len(expression.name)
            + 2
            + sum(_rendered_size_upper_bound(argument) + 1 for argument in expression.arguments)
        )
    if isinstance(expression, Sum):
        parts = (expression.body, expression.lower, expression.upper)
        return 16 + len(expression.index) + sum(_rendered_size_upper_bound(part) for part in parts)
    return (
        3
        + _rendered_size_upper_bound(expression.left)
        + _rendered_size_upper_bound(expression.right)
    )


def render_operations(tally: SymbolicTally, budget: WorkRenderBudget) -> SymbolicOperationCounts:
    return SymbolicOperationCounts(
        additions=render_work(tally.additions, budget),
        subtractions=render_work(tally.subtractions, budget),
        multiplications=render_work(tally.multiplications, budget),
        divisions=render_work(tally.divisions, budget),
        powers=render_work(tally.powers, budget),
    )


def render_invocations(
    invocations: dict[str, Expression], budget: WorkRenderBudget
) -> dict[str, str]:
    return {name: render_work(count, budget) for name, count in sorted(invocations.items())}


def map_analysis(
    analysis: WorkAnalysis, transform: Callable[[Expression], Expression]
) -> WorkAnalysis:
    return WorkAnalysis(
        operations=SymbolicTally(
            additions=transform(analysis.operations.additions),
            subtractions=transform(analysis.operations.subtractions),
            multiplications=transform(analysis.operations.multiplications),
            divisions=transform(analysis.operations.divisions),
            powers=transform(analysis.operations.powers),
        ),
        opaque_work=transform(analysis.opaque_work),
        invocations={name: transform(count) for name, count in analysis.invocations.items()},
        unknown_costs=set(analysis.unknown_costs),
        unresolved=set(analysis.unresolved),
        direct_work_blockers=set(analysis.direct_work_blockers),
    )


def aggregate_analysis(
    analysis: WorkAnalysis,
    index: str,
    lower: Expression,
    upper: Expression,
    context: WorkContext,
    label: str,
) -> tuple[WorkAnalysis, str | None]:
    """Aggregate over an output domain without erasing index-dependent work."""
    count, unresolved = cardinality(lower, upper, context, label)

    return map_analysis(
        analysis,
        lambda value: _aggregate_value(value, index, lower, upper, count),
    ), unresolved


def _aggregate_value(
    value: Expression,
    index: str,
    lower: Expression,
    upper: Expression,
    count: Expression,
) -> Expression:
    if index in _free_symbol_names(value):
        return factor_independent(Sum(value, index, lower, upper), index)
    return _multiply(count, value)


def factor_independent(expression: Expression, index: str) -> Expression:
    """Apply the one deterministic factoring rule needed for indexed work."""
    if not isinstance(expression, Sum) or not isinstance(expression.body, BinaryExpression):
        return expression
    body = expression.body
    if body.operator is not BinaryOperator.MULTIPLY:
        return expression
    left_depends = index in _free_symbol_names(body.left)
    right_depends = index in _free_symbol_names(body.right)
    if left_depends == right_depends:
        return expression
    independent, dependent = (body.right, body.left) if left_depends else (body.left, body.right)
    return _multiply(independent, Sum(dependent, index, expression.lower, expression.upper))


def _free_symbol_names(
    expression: Expression, bound: frozenset[str] = frozenset()
) -> set[str]:
    if isinstance(expression, Symbol):
        return set() if expression.name in bound else {expression.name}
    if isinstance(expression, Sum):
        return (
            _free_symbol_names(expression.lower, bound)
            | _free_symbol_names(expression.upper, bound)
            | _free_symbol_names(expression.body, bound | {expression.index})
        )
    result: set[str] = set()
    for child in _expression_children(expression):
        result.update(_free_symbol_names(child, bound))
    return result


def replace_exact(
    expression: Expression, target: Expression, replacement: Expression
) -> tuple[Expression, bool]:
    replacement_symbols = _free_symbol_names(target) | _free_symbol_names(replacement)
    changed = False

    def visit(value: Expression, bound: frozenset[str]) -> Expression:
        nonlocal changed
        if value == target and not (replacement_symbols & bound):
            changed = True
            return replacement
        if isinstance(value, IndexedValue):
            return IndexedValue(
                value.name, tuple(visit(item, bound) for item in value.indices)
            )
        if isinstance(value, Call):
            return Call(value.name, tuple(visit(item, bound) for item in value.arguments))
        if isinstance(value, Sum):
            return Sum(
                visit(value.body, bound | {value.index}),
                value.index,
                visit(value.lower, bound),
                visit(value.upper, bound),
            )
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator, visit(value.left, bound), visit(value.right, bound)
            )
        return value

    return visit(expression, frozenset()), changed


def _expression_children(expression: Expression) -> tuple[Expression, ...]:
    if isinstance(expression, BinaryExpression):
        return (expression.left, expression.right)
    if isinstance(expression, IndexedValue):
        return expression.indices
    if isinstance(expression, Call):
        return expression.arguments
    if isinstance(expression, Sum):
        return (expression.lower, expression.upper, expression.body)
    return ()


def expand_function_values(
    expression: Expression, definitions: dict[str, FunctionRule]
) -> Expression:
    """Expand validated acyclic mathematical definitions in derived work values."""
    if isinstance(expression, IndexedValue):
        result: Expression = IndexedValue(
            expression.name,
            tuple(expand_function_values(item, definitions) for item in expression.indices),
        )
    elif isinstance(expression, Call):
        arguments = tuple(
            expand_function_values(item, definitions) for item in expression.arguments
        )
        definition = definitions.get(expression.name)
        if definition is None:
            result = Call(expression.name, arguments)
        else:
            result = expand_function_values(
                substitute(
                    definition.body,
                    dict(zip(definition.parameters, arguments, strict=True)),
                    max_nodes=MAX_WORK_NODES,
                ),
                definitions,
            )
    elif isinstance(expression, Sum):
        result = Sum(
            expand_function_values(expression.body, definitions),
            expression.index,
            expand_function_values(expression.lower, definitions),
            expand_function_values(expression.upper, definitions),
        )
    elif isinstance(expression, BinaryExpression):
        result = BinaryExpression(
            expression.operator,
            expand_function_values(expression.left, definitions),
            expand_function_values(expression.right, definitions),
        )
    else:
        result = expression
    if expression_node_count(result) > MAX_WORK_NODES:
        raise ExpressionTooComplex("definition-expanded work exceeds its structural bound")
    return result


def simplify_constants(expression: Expression) -> Expression:
    if isinstance(expression, IndexedValue):
        return IndexedValue(
            expression.name, tuple(simplify_constants(item) for item in expression.indices)
        )
    if isinstance(expression, Call):
        arguments = tuple(simplify_constants(item) for item in expression.arguments)
        if expression.name == "Max" and all(isinstance(item, IntegerLiteral) for item in arguments):
            return IntegerLiteral(
                max(item.value for item in arguments if isinstance(item, IntegerLiteral))
            )
        return Call(expression.name, arguments)
    if isinstance(expression, Sum):
        return Sum(
            simplify_constants(expression.body),
            expression.index,
            simplify_constants(expression.lower),
            simplify_constants(expression.upper),
        )
    if not isinstance(expression, BinaryExpression):
        return expression
    left = simplify_constants(expression.left)
    right = simplify_constants(expression.right)
    if isinstance(left, IntegerLiteral) and isinstance(right, IntegerLiteral):
        if expression.operator is BinaryOperator.ADD:
            return IntegerLiteral(left.value + right.value)
        if expression.operator is BinaryOperator.SUBTRACT:
            return IntegerLiteral(left.value - right.value)
        if expression.operator is BinaryOperator.MULTIPLY:
            return IntegerLiteral(left.value * right.value)
        if expression.operator is BinaryOperator.POWER and right.value >= 0:
            return IntegerLiteral(left.value**right.value)
    return BinaryExpression(expression.operator, left, right)


def substitute_analysis(
    analysis: WorkAnalysis,
    replacements: dict[str, Expression],
) -> WorkAnalysis:
    operations = SymbolicTally(
        additions=substitute(
            analysis.operations.additions, replacements, max_nodes=MAX_WORK_NODES
        ),
        subtractions=substitute(
            analysis.operations.subtractions, replacements, max_nodes=MAX_WORK_NODES
        ),
        multiplications=substitute(
            analysis.operations.multiplications, replacements, max_nodes=MAX_WORK_NODES
        ),
        divisions=substitute(
            analysis.operations.divisions, replacements, max_nodes=MAX_WORK_NODES
        ),
        powers=substitute(analysis.operations.powers, replacements, max_nodes=MAX_WORK_NODES),
    )
    opaque_work = substitute(analysis.opaque_work, replacements, max_nodes=MAX_WORK_NODES)
    invocations = {
        name: substitute(count, replacements, max_nodes=MAX_WORK_NODES)
        for name, count in analysis.invocations.items()
    }
    blockers = set(analysis.direct_work_blockers)
    substituted_work = (
        operations.additions,
        operations.subtractions,
        operations.multiplications,
        operations.divisions,
        operations.powers,
        opaque_work,
        *invocations.values(),
    )
    if any(_contains_infinity(value) for value in substituted_work):
        blockers.add(_INFINITY_WORK_BLOCKER)
    return WorkAnalysis(
        operations=operations,
        opaque_work=opaque_work,
        invocations=invocations,
        unknown_costs=set(analysis.unknown_costs),
        unresolved=set(analysis.unresolved),
        direct_work_blockers=blockers,
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
    result = map_analysis(
        body,
        lambda value: _aggregate_value(
            value,
            expression.index,
            expression.lower,
            expression.upper,
            count,
        ),
    )
    reduction = (
        _subtract(count, _ONE)
        if is_positive_expression(count, context)
        else _max_zero(_subtract(count, _ONE))
    )
    result.operations = result.operations.combine(SymbolicTally(additions=reduction))
    if unresolved is not None:
        result.unresolved.add(unresolved)
        if unresolved == "infinite iterator has no finite direct-evaluation work":
            result.direct_work_blockers.add(unresolved)
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
        internal = substitute(definition.body, placeholders, max_nodes=MAX_WORK_NODES)
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
            substitute(primitive.work, replacements, max_nodes=MAX_WORK_NODES),
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
    return (isinstance(expression, IntegerLiteral) and expression.value == 1) or (isinstance(expression, RationalLiteral) and expression.numerator == expression.positive_denominator)  # noqa: E501
