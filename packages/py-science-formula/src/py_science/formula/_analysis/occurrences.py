"""Bounded structural occurrence facts and legacy diagnostic projection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Expression,
    IndexedValue,
    Let,
    Sum,
    Symbol,
    expression_children,
)
from py_science.formula.sympy_backend import NormalizationError, render

MAX_OCCURRENCE_INSPECTIONS = 16_384


class _TraversalExhausted(RuntimeError):
    pass

@dataclass(frozen=True, slots=True)
class _ScopeBinding:
    """One lexical binding with enough identity to compare evaluation scopes."""

    name: str
    path: tuple[int, ...]
    lower: Expression | None = None
    upper: Expression | None = None
    value: Expression | None = None


@dataclass(frozen=True, slots=True)
class _EvaluationScope:
    """The lexical/output interface required to evaluate an occurrence."""

    output_indices: tuple[str, ...]
    output_bindings: tuple[_ScopeBinding, ...]
    binders: tuple[_ScopeBinding, ...]


@dataclass(frozen=True, slots=True)
class _Occurrence:
    """One structural expression occurrence in a retained computation."""

    target: str
    path: tuple[int, ...]
    expression: Expression
    free_symbols: frozenset[str]
    binders: tuple[str, ...]
    scope: _EvaluationScope


def _detect_occurrences(
    target: str,
    expression: Expression,
    producers: Mapping[str, object],
    *,
    output_indices: tuple[str, ...] = (),
    output_domains: Mapping[str, tuple[Expression, Expression]] | None = None,
    max_nodes: int = MAX_OCCURRENCE_INSPECTIONS,
) -> tuple[_Occurrence, ...]:
    """Return bounded, deterministic occurrences without changing public analysis."""
    occurrences: list[_Occurrence] = []
    remaining = max_nodes
    output_domain_map = output_domains or {}
    output_bindings = tuple(
        _ScopeBinding(
            name=name,
            path=(position,),
            lower=output_domain_map.get(name, (None, None))[0],
            upper=output_domain_map.get(name, (None, None))[1],
        )
        for position, name in enumerate(output_indices)
    )

    def visit(
        node: Expression,
        path: tuple[int, ...],
        bound: tuple[_ScopeBinding, ...],
        lexical_bound: frozenset[str],
    ) -> None:
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise _TraversalExhausted("occurrence traversal exceeds its node bound")
        is_named_reference = isinstance(node, (Symbol, IndexedValue)) and node.name in producers
        if is_named_reference:
            if isinstance(node, IndexedValue):
                for index, child in enumerate(node.indices):
                    visit(child, (*path, index), bound, lexical_bound)
            return
        binder_names = tuple(item.name for item in bound)
        if isinstance(node, (BinaryExpression, Call, Sum, Let)):
            occurrences.append(
                _Occurrence(
                    target=target,
                    path=path,
                    expression=node,
                    free_symbols=frozenset(
                        _free_symbols(
                            node,
                            frozenset((*output_indices, *binder_names)) | lexical_bound,
                        )
                    ),
                    binders=binder_names,
                    scope=_EvaluationScope(output_indices, output_bindings, bound),
                )
            )
        if isinstance(node, Sum):
            # Bounds are evaluated outside the new binder; only the body owns it.
            visit(node.lower, (*path, 0), bound, lexical_bound)
            visit(node.upper, (*path, 1), bound, lexical_bound)
            binding = _ScopeBinding(node.index, path, node.lower, node.upper)
            visit(node.body, (*path, 2), (*bound, binding), lexical_bound)
            return
        if isinstance(node, Let):
            visit(node.value, (*path, 0), bound, lexical_bound)
            binding = _ScopeBinding(node.name, path, value=node.value)
            visit(
                node.body,
                (*path, 1),
                (*bound, binding),
                lexical_bound | {node.name},
            )
            return
        for index, child in enumerate(expression_children(node)):
            visit(child, (*path, index), bound, lexical_bound)

    visit(expression, (), (), frozenset())
    return tuple(occurrences)


def _extraction_opportunities(  # pyright: ignore[reportUnusedFunction]
    target: str,
    expression: Expression,
    producers: Mapping[str, object],
    *,
    output_indices: tuple[str, ...] = (),
    output_domains: Mapping[str, tuple[Expression, Expression]] | None = None,
) -> tuple[str, ...]:
    """Render the legacy extraction diagnostic from typed occurrences."""
    try:
        occurrences = _detect_occurrences(
            target,
            expression,
            producers,
            output_indices=output_indices,
            output_domains=output_domains,
        )
    except _TraversalExhausted:
        # Diagnostics have always been best-effort; exhaustion must not alter analysis.
        return ()
    counts: Counter[Expression] = Counter(item.expression for item in occurrences)
    opportunities: list[str] = []
    for node, count in counts.items():
        if count > 1:
            try:
                text = render(node).sympy
            except NormalizationError:
                continue
            opportunities.append(
                f"equation {target}: extract repeated `{text}` ({count} occurrences)"
            )
    return tuple(sorted(opportunities))


def _free_symbols(expression: Expression, bound: frozenset[str] = frozenset()) -> set[str]:
    if isinstance(expression, Symbol):
        return set() if expression.name in bound else {expression.name}
    if isinstance(expression, IndexedValue):
        result = set() if expression.name in bound else {expression.name}
        for index in expression.indices:
            result.update(_free_symbols(index, bound))
        return result
    if isinstance(expression, Sum):
        return (
            _free_symbols(expression.lower, bound)
            | _free_symbols(expression.upper, bound)
            | _free_symbols(expression.body, bound | {expression.index})
        )
    if isinstance(expression, Let):
        return _free_symbols(expression.value, bound) | _free_symbols(
            expression.body, bound | {expression.name}
        )
    result: set[str] = set()
    for child in expression_children(expression):
        result.update(_free_symbols(child, bound))
    return result
