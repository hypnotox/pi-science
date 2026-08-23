# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Private optimizer owner."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import permutations
from typing import Literal

from py_science.formula._analysis.occurrences import (
    _EvaluationScope,
    _free_symbols,
    _Occurrence,
)
from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    IndexedValue,
    IntegerLiteral,
    Let,
    Relationship,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
    substitute,
)
from py_science.formula.models import (
    OptimizationKind,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.sympy_backend import (
    bounded_factor_candidate,
    render,
)

from .budgets import MAX_OPTIMIZATION_TRANSFORM_NODES


@dataclass(frozen=True, slots=True)
class _CandidateComputation:
    """One local proposal; only the common verifier can turn it public."""

    kind: Literal[
        "repeated_subexpression",
        "repeated_call",
        "reciprocal_reuse",
        "factoring",
        "redundant_operation_removal",
        "iterator_invariant_hoisting",
        "cross_equation_sharing",
        "horner",
        "finite_polynomial_sum_v1",
    ]
    target: str
    original: Expression
    proposed: Expression
    occurrences: tuple[_Occurrence, ...]
    transformed_targets: tuple[tuple[str, Expression, Expression], ...] = ()
    intermediate_name: str | None = None
    intermediate_expression: Expression | None = None
    intermediate_scope: _EvaluationScope | None = None


@dataclass(frozen=True, slots=True)
class _CandidateDescriptor:
    """Stable lightweight proposal recipe, materialized only by the scheduler."""

    kind: OptimizationKind
    sort_key: tuple[object, ...]
    factory: Callable[[], _CandidateComputation]


def _all_symbol_names(expression: Expression) -> set[str]:
    result: set[str] = set()
    if isinstance(expression, (Symbol, IndexedValue, Call)):
        result.add(expression.name)
    if isinstance(expression, Sum):
        result.add(expression.index)
    if isinstance(expression, Let):
        result.add(expression.name)
    for child in expression_children(expression):
        result.update(_all_symbol_names(child))
    return result


def _replace_paths(
    expression: Expression, paths: Iterable[tuple[int, ...]], replacement: Expression
) -> Expression:
    selected = frozenset(paths)

    def visit(node: Expression, path: tuple[int, ...]) -> Expression:
        if path in selected:
            return replacement
        if isinstance(node, BinaryExpression):
            return BinaryExpression(
                node.operator, visit(node.left, (*path, 0)), visit(node.right, (*path, 1))
            )
        if isinstance(node, Call):
            return Call(
                node.name,
                tuple(visit(child, (*path, index)) for index, child in enumerate(node.arguments)),
            )
        if isinstance(node, IndexedValue):
            return IndexedValue(
                node.name,
                tuple(visit(child, (*path, index)) for index, child in enumerate(node.indices)),
            )
        if isinstance(node, Sum):
            return Sum(
                visit(node.body, (*path, 2)),
                node.index,
                visit(node.lower, (*path, 0)),
                visit(node.upper, (*path, 1)),
            )
        if isinstance(node, Let):
            return Let(
                node.name,
                visit(node.value, (*path, 0)),
                visit(node.body, (*path, 1)),
            )
        return node

    return visit(expression, ())


def _smallest_scope(expression: Expression, scope: _EvaluationScope) -> _EvaluationScope:
    raw = _free_symbols(expression)
    selected_binders = {binding.name for binding in scope.binders if binding.name in raw}
    changed = True
    while changed:
        changed = False
        for binding in scope.binders:
            if binding.name not in selected_binders:
                continue
            dependencies: set[str] = set()
            for value in (binding.lower, binding.upper, binding.value):
                if value is not None:
                    dependencies.update(_free_symbols(value))
            before = len(selected_binders)
            selected_binders.update(
                item.name for item in scope.binders if item.name in dependencies
            )
            changed = changed or len(selected_binders) != before
    binders = tuple(binding for binding in scope.binders if binding.name in selected_binders)
    selected_outputs = {binding.name for binding in scope.output_bindings if binding.name in raw}
    # A predecessor used by a selected output bound is part of the evaluation
    # interface even when it does not occur in the intermediate expression.
    changed = True
    while changed:
        changed = False
        for binding in scope.output_bindings:
            if binding.name not in selected_outputs:
                continue
            dependencies: set[str] = set()
            if binding.lower is not None:
                dependencies.update(_free_symbols(binding.lower))
            if binding.upper is not None:
                dependencies.update(_free_symbols(binding.upper))
            before = len(selected_outputs)
            selected_outputs.update(
                item.name for item in scope.output_bindings if item.name in dependencies
            )
            changed = changed or len(selected_outputs) != before
    outputs = tuple(
        binding for binding in scope.output_bindings if binding.name in selected_outputs
    )
    return _EvaluationScope(tuple(binding.name for binding in outputs), outputs, binders)


def _generated_name(computed: RetainedComputation) -> str:
    names: set[str] = {
        *computed.producers,
        *computed.work_context.definitions,
        *computed.work_context.primitives,
        *computed.work_context.variable_domains,
        *(definition.name for definition in computed.knowledge.definitions),
    }
    if computed.expression is not None:
        names.update(_all_symbol_names(computed.expression))
    for equation in computed.equations:
        names.update(_all_symbol_names(equation.formula.right))
        names.update(equation.domain_order)
        names.add(equation.name)
    index = 1
    while f"optimization_tmp_{index}" in names:
        index += 1
    return f"optimization_tmp_{index}"


def _target_inputs(
    computed: RetainedComputation,
) -> tuple[
    tuple[str, Expression, tuple[str, ...], Mapping[str, tuple[Expression, Expression]]], ...
]:
    if computed.expression is not None:
        return (("expression", computed.expression, (), {}),)
    return tuple(
        (
            equation.name,
            equation.formula.right,
            equation.domain_order,
            {domain.index: (domain.lower, domain.upper) for domain in equation.output_domains},
        )
        for equation in computed.equations
    )


def _canonical_output_index_names(arity: int, reserved_names: set[str]) -> tuple[str, ...]:
    reserved = set(reserved_names)
    result: list[str] = []
    for position in range(arity):
        base = f"optimization_index_{position}"
        name = base
        suffix = 0
        while name in reserved:
            suffix += 1
            name = f"{base}_{suffix}"
        reserved.add(name)
        result.append(name)
    return tuple(result)


def _canonical_output_expression(
    expression: Expression,
    output_indices: tuple[str, ...],
    reserved_names: set[str] | None = None,
    canonical_output_indices: tuple[str, ...] | None = None,
    free_names: Mapping[str, str] | None = None,
) -> Expression:
    """Normalize positional output and lexical binder names without algebra."""
    reserved = set(reserved_names or ()) | _all_symbol_names(expression)
    if canonical_output_indices is None:
        canonical_output_indices = _canonical_output_index_names(len(output_indices), reserved)
    assert len(canonical_output_indices) == len(output_indices)
    reserved.update(canonical_output_indices)

    def fresh(base: str) -> str:
        name = base
        position = 0
        while name in reserved:
            position += 1
            name = f"{base}_{position}"
        reserved.add(name)
        return name

    def visit(
        value: Expression,
        names: Mapping[str, str],
        path: tuple[int, ...],
    ) -> Expression:
        if isinstance(value, Symbol):
            return Symbol(names.get(value.name, value.name))
        if isinstance(value, IndexedValue):
            return IndexedValue(
                names.get(value.name, value.name),
                tuple(
                    visit(item, names, (*path, position))
                    for position, item in enumerate(value.indices)
                ),
            )
        if isinstance(value, Call):
            return Call(
                value.name,
                tuple(
                    visit(item, names, (*path, position))
                    for position, item in enumerate(value.arguments)
                ),
            )
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator,
                visit(value.left, names, (*path, 0)),
                visit(value.right, names, (*path, 1)),
            )
        if isinstance(value, Sum):
            canonical = fresh("optimization_sum_" + "_".join(str(item) for item in path or (0,)))
            inner = dict(names)
            inner[value.index] = canonical
            return Sum(
                visit(value.body, inner, (*path, 2)),
                canonical,
                visit(value.lower, names, (*path, 0)),
                visit(value.upper, names, (*path, 1)),
            )
        if isinstance(value, Let):
            canonical = fresh("optimization_let_" + "_".join(str(item) for item in path or (0,)))
            inner = dict(names)
            inner[value.name] = canonical
            return Let(
                canonical,
                visit(value.value, names, (*path, 0)),
                visit(value.body, inner, (*path, 1)),
            )
        return value

    names = dict(free_names or {})
    names.update(zip(output_indices, canonical_output_indices, strict=True))
    return visit(expression, names, ())


def _generated_let_variants(
    expression: Expression, generated_names: frozenset[str]
) -> tuple[Expression, ...]:
    """Enumerate bounded dependency-valid orders for a generated Let chain."""
    bindings: list[tuple[str, Expression]] = []
    body = expression
    while isinstance(body, Let) and body.name in generated_names:
        bindings.append((body.name, body.value))
        body = body.body
    if len(bindings) < 2:
        return (expression,)

    bound_names = {name for name, _value in bindings}
    variants: list[Expression] = []
    for order in permutations(bindings):
        available: set[str] = set()
        valid = True
        for name, value in order:
            if not (_free_symbols(value) & bound_names) <= available:
                valid = False
                break
            available.add(name)
        if not valid:
            continue
        reordered = body
        for name, value in reversed(order):
            reordered = Let(name, value, reordered)
        variants.append(reordered)
    return tuple(variants) or (expression,)


def _cross_equation_descriptors(
    computed: RetainedComputation,
    occurrences_by_target: Mapping[str, tuple[_Occurrence, ...]],
    generated_name: str,
) -> tuple[_CandidateDescriptor, ...]:
    if computed.expression is not None or len(computed.equations) < 2:
        return ()
    equations = {item.name: item for item in computed.equations}
    canonical_reserved: set[str] = set()
    for equation in computed.equations:
        canonical_reserved.update(_all_symbol_names(equation.formula.right))
        for domain in equation.output_domains:
            canonical_reserved.update(_all_symbol_names(domain.lower))
            canonical_reserved.update(_all_symbol_names(domain.upper))
    grouped: dict[
        tuple[int, Expression, tuple[tuple[Expression, Expression], ...]],
        list[_Occurrence],
    ] = defaultdict(list)
    for target, occurrences in occurrences_by_target.items():
        equation = equations[target]
        # Equation-local constraints cannot be attached to one shared producer.
        if equation.submitted_constraints:
            continue
        canonical_output_indices = _canonical_output_index_names(
            len(equation.domain_order), canonical_reserved
        )
        replacements: dict[str, Expression] = {
            name: Symbol(canonical)
            for name, canonical in zip(equation.domain_order, canonical_output_indices, strict=True)
        }
        domain_signature = tuple(
            (
                substitute(domain.lower, replacements, max_nodes=MAX_OPTIMIZATION_TRANSFORM_NODES),
                substitute(domain.upper, replacements, max_nodes=MAX_OPTIMIZATION_TRANSFORM_NODES),
            )
            for domain in equation.output_domains
        )
        for occurrence in occurrences:
            if occurrence.scope.binders or expression_node_count(occurrence.expression) < 2:
                continue
            grouped[
                (
                    len(equation.domain_order),
                    _canonical_output_expression(
                        occurrence.expression,
                        equation.domain_order,
                        canonical_reserved,
                        canonical_output_indices,
                    ),
                    domain_signature,
                )
            ].append(occurrence)

    result: list[_CandidateDescriptor] = []
    for (_arity, _canonical, _domains), grouped_occurrences in grouped.items():
        by_target: dict[str, _Occurrence] = {}
        for occurrence in grouped_occurrences:
            by_target.setdefault(occurrence.target, occurrence)
        if len(by_target) < 2:
            continue
        selected = tuple(by_target[name] for name in sorted(by_target))
        target_names = frozenset(by_target)
        # A producer depending on one of its consumers would introduce a cycle.
        producer_dependencies = {
            computed.producers[name].equation_name
            for name in _all_symbol_names(selected[0].expression)
            if name in computed.producers
        }
        if producer_dependencies & target_names:
            continue
        first = selected[0]
        first_equation = equations[first.target]
        raw = _free_symbols(first.expression)
        interface_positions = tuple(
            position for position, name in enumerate(first_equation.domain_order) if name in raw
        )
        transformed: list[tuple[str, Expression, Expression]] = []
        compatible = True
        for occurrence in selected:
            equation = equations[occurrence.target]
            used_positions = tuple(
                position
                for position, name in enumerate(equation.domain_order)
                if name in _free_symbols(occurrence.expression)
            )
            if used_positions != interface_positions:
                compatible = False
                break
            arguments = tuple(
                Symbol(equation.domain_order[position]) for position in interface_positions
            )
            reference: Expression = (
                IndexedValue(generated_name, arguments) if arguments else Symbol(generated_name)
            )
            transformed.append(
                (
                    occurrence.target,
                    equation.formula.right,
                    _replace_paths(equation.formula.right, (occurrence.path,), reference),
                )
            )
        if not compatible:
            continue
        result.append(
            _descriptor_from_recipe(
                kind="cross_equation_sharing",
                target=first.target,
                original=transformed[0][1],
                proposed=transformed[0][2],
                occurrences=selected,
                transformed_targets=tuple(transformed),
                intermediate_name=generated_name,
                intermediate_expression=first.expression,
                intermediate_scope=_smallest_scope(first.expression, first.scope),
            )
        )
    return tuple(result)


def _generated_reference(name: str, scope: _EvaluationScope) -> Expression:
    indices = tuple(Symbol(index) for index in scope.output_indices)
    return IndexedValue(name, indices) if indices else Symbol(name)


def _wrap_complete_let(expression: Expression, candidate: _CandidateComputation) -> Expression:
    """Place a lexical candidate at the scope where its value is evaluated."""
    name = candidate.intermediate_name
    intermediate = candidate.intermediate_expression
    scope = candidate.intermediate_scope
    assert name is not None and intermediate is not None and scope is not None
    binding = scope.binders[-1:]
    path = ()
    if binding:
        owner = binding[0]
        path = (*owner.path, 1 if owner.value is not None else 2)

    def lexicalize(value: Expression) -> Expression:
        if isinstance(value, (Symbol, IndexedValue)) and value.name == name:
            return Symbol(name)
        if isinstance(value, BinaryExpression):
            return BinaryExpression(value.operator, lexicalize(value.left), lexicalize(value.right))
        if isinstance(value, Call):
            return Call(value.name, tuple(lexicalize(item) for item in value.arguments))
        if isinstance(value, IndexedValue):
            return IndexedValue(value.name, tuple(lexicalize(item) for item in value.indices))
        if isinstance(value, Sum):
            return Sum(
                lexicalize(value.body),
                value.index,
                lexicalize(value.lower),
                lexicalize(value.upper),
            )
        if isinstance(value, Let):
            return Let(value.name, lexicalize(value.value), lexicalize(value.body))
        return value

    def visit(value: Expression, current: tuple[int, ...]) -> Expression:
        if current == path:
            return Let(name, intermediate, lexicalize(value))
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator,
                visit(value.left, (*current, 0)),
                visit(value.right, (*current, 1)),
            )
        if isinstance(value, Call):
            return Call(
                value.name,
                tuple(visit(item, (*current, index)) for index, item in enumerate(value.arguments)),
            )
        if isinstance(value, IndexedValue):
            return IndexedValue(
                value.name,
                tuple(visit(item, (*current, index)) for index, item in enumerate(value.indices)),
            )
        if isinstance(value, Sum):
            return Sum(
                visit(value.body, (*current, 2)),
                value.index,
                visit(value.lower, (*current, 0)),
                visit(value.upper, (*current, 1)),
            )
        if isinstance(value, Let):
            return Let(
                value.name,
                visit(value.value, (*current, 0)),
                visit(value.body, (*current, 1)),
            )
        return value

    return visit(expression, ())


def _scope_sort_key(scope: _EvaluationScope | None) -> tuple[object, ...]:
    if scope is None:
        return ()
    return (
        scope.output_indices,
        tuple(
            (
                binding.name,
                binding.path,
                render(binding.lower).sympy if binding.lower is not None else "",
                render(binding.upper).sympy if binding.upper is not None else "",
            )
            for binding in scope.output_bindings
        ),
        tuple(
            (
                binding.name,
                binding.path,
                render(binding.lower).sympy if binding.lower is not None else "",
                render(binding.upper).sympy if binding.upper is not None else "",
                render(binding.value).sympy if binding.value is not None else "",
            )
            for binding in scope.binders
        ),
    )


def _descriptor_sort_key(
    kind: OptimizationKind,
    target: str,
    original: Expression,
    proposed: Expression,
    occurrences: tuple[_Occurrence, ...] = (),
    transformed_targets: tuple[tuple[str, Expression, Expression], ...] = (),
    intermediate_expression: Expression | None = None,
    intermediate_scope: _EvaluationScope | None = None,
) -> tuple[object, ...]:
    transformations = transformed_targets or ((target, original, proposed),)
    return (
        kind,
        tuple(
            (name, render(before).sympy, render(after).sympy)
            for name, before, after in transformations
        ),
        tuple((item.target, item.path, item.binders) for item in occurrences),
        render(intermediate_expression).sympy if intermediate_expression is not None else "",
        _scope_sort_key(intermediate_scope),
    )


def _horner_candidate(
    target: str, original: Expression, occurrence: _Occurrence, rendered: str
) -> _CandidateComputation:
    """Parse the bounded Horner rendering only after scheduler admission."""
    parsed = parse_expression(rendered)
    assert not isinstance(parsed, (ParseFailure, Equation, Relationship))
    return _CandidateComputation(
        kind="horner",
        target=target,
        original=original,
        proposed=_replace_paths(original, (occurrence.path,), parsed),
        occurrences=(occurrence,),
    )


def _replacement_descriptor(
    *,
    kind: OptimizationKind,
    target: str,
    original: Expression,
    occurrences: tuple[_Occurrence, ...],
    replacement: Expression,
) -> _CandidateDescriptor:
    """Retain a target/path/replacement recipe and defer structural replacement."""
    paths = tuple(item.path for item in occurrences)
    return _CandidateDescriptor(
        kind,
        (kind, target, render(original).sympy, paths, render(replacement).sympy),
        lambda: _CandidateComputation(
            kind=kind,
            target=target,
            original=original,
            proposed=_replace_paths(original, paths, replacement),
            occurrences=occurrences,
        ),
    )


def _generated_replacement_descriptor(
    *,
    kind: OptimizationKind,
    target: str,
    original: Expression,
    occurrences: tuple[_Occurrence, ...],
    generated_name: str,
    intermediate_expression: Expression,
    intermediate_scope: _EvaluationScope,
) -> _CandidateDescriptor:
    """Retain generated-reference placement data until scheduled materialization."""
    paths = tuple(item.path for item in occurrences)
    return _CandidateDescriptor(
        kind,
        (
            kind,
            target,
            render(original).sympy,
            paths,
            generated_name,
            render(intermediate_expression).sympy,
            _scope_sort_key(intermediate_scope),
        ),
        lambda: _CandidateComputation(
            kind=kind,
            target=target,
            original=original,
            proposed=_replace_paths(
                original, paths, _generated_reference(generated_name, intermediate_scope)
            ),
            occurrences=occurrences,
            intermediate_name=generated_name,
            intermediate_expression=intermediate_expression,
            intermediate_scope=intermediate_scope,
        ),
    )


def _descriptor_from_recipe(
    *,
    kind: OptimizationKind,
    target: str,
    original: Expression,
    proposed: Expression,
    occurrences: tuple[_Occurrence, ...] = (),
    transformed_targets: tuple[tuple[str, Expression, Expression], ...] = (),
    intermediate_name: str | None = None,
    intermediate_expression: Expression | None = None,
    intermediate_scope: _EvaluationScope | None = None,
) -> _CandidateDescriptor:
    """Capture a complete candidate recipe without constructing it during discovery."""
    return _CandidateDescriptor(
        kind,
        _descriptor_sort_key(
            kind,
            target,
            original,
            proposed,
            occurrences,
            transformed_targets,
            intermediate_expression,
            intermediate_scope,
        ),
        lambda: _CandidateComputation(
            kind,
            target,
            original,
            proposed,
            occurrences,
            transformed_targets,
            intermediate_name,
            intermediate_expression,
            intermediate_scope,
        ),
    )


def _neutral_replacement(expression: Expression) -> Expression | None:
    if not isinstance(expression, BinaryExpression):
        return None
    left, right = expression.left, expression.right
    if isinstance(right, IntegerLiteral):
        if right.value == 0 and expression.operator in {
            BinaryOperator.ADD,
            BinaryOperator.SUBTRACT,
        }:
            return left
        if right.value == 1 and expression.operator in {
            BinaryOperator.MULTIPLY,
            BinaryOperator.DIVIDE,
            BinaryOperator.POWER,
        }:
            return left
    if isinstance(left, IntegerLiteral):
        if left.value == 0 and expression.operator is BinaryOperator.ADD:
            return right
        if left.value == 1 and expression.operator is BinaryOperator.MULTIPLY:
            return right
    return None


def _factor_term(expression: Expression) -> tuple[Expression, Expression] | None:
    if (
        not isinstance(expression, BinaryExpression)
        or expression.operator is not BinaryOperator.MULTIPLY
    ):
        return None
    return expression.left, expression.right


def _factored(expression: Expression) -> Expression | None:
    if not isinstance(expression, BinaryExpression) or expression.operator not in {
        BinaryOperator.ADD,
        BinaryOperator.SUBTRACT,
    }:
        return None
    left = _factor_term(expression.left)
    right = _factor_term(expression.right)
    if left is None or right is None:
        return None
    common: Expression | None = None
    left_rest: Expression | None = None
    right_rest: Expression | None = None
    for left_position, left_item in enumerate(left):
        for right_position, right_item in enumerate(right):
            if left_item == right_item:
                common = left_item
                left_rest = left[1 - left_position]
                right_rest = right[1 - right_position]
                break
        if common is not None:
            break
    if common is None or left_rest is None or right_rest is None:
        return None
    rendered = bounded_factor_candidate(expression)
    if rendered is None:
        return None
    parsed = parse_expression(rendered)
    if isinstance(parsed, (ParseFailure, Equation, Relationship)):
        return None
    return parsed
