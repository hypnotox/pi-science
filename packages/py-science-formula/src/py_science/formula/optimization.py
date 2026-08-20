"""Private bounded occurrence and scope detection for formula analysis."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Expression,
    IndexedValue,
    Sum,
    Symbol,
    expression_children,
)
from py_science.formula.models import AnalysisRequest, OptimizationReport
from py_science.formula.sympy_backend import NormalizationError, render


@dataclass(frozen=True, slots=True)
class _ScopeBinding:
    """One lexical binding with enough identity to compare evaluation scopes."""

    name: str
    path: tuple[int, ...]
    lower: Expression | None = None
    upper: Expression | None = None


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


class _TraversalExhausted(RuntimeError):
    pass


def _detect_occurrences(
    target: str,
    expression: Expression,
    producers: Mapping[str, object],
    *,
    output_indices: tuple[str, ...] = (),
    output_domains: Mapping[str, tuple[Expression, Expression]] | None = None,
    max_nodes: int = 16_384,
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
    ) -> None:
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise _TraversalExhausted("occurrence traversal exceeds its node bound")
        is_named_reference = isinstance(node, (Symbol, IndexedValue)) and node.name in producers
        if is_named_reference:
            if isinstance(node, IndexedValue):
                for index, child in enumerate(node.indices):
                    visit(child, (*path, index), bound)
            return
        binder_names = tuple(item.name for item in bound)
        if isinstance(node, (BinaryExpression, Call, Sum)):
            occurrences.append(
                _Occurrence(
                    target=target,
                    path=path,
                    expression=node,
                    free_symbols=frozenset(
                        _free_symbols(
                            node,
                            frozenset((*output_indices, *binder_names)),
                        )
                    ),
                    binders=binder_names,
                    scope=_EvaluationScope(output_indices, output_bindings, bound),
                )
            )
        if isinstance(node, Sum):
            # Bounds are evaluated outside the new binder; only the body owns it.
            visit(node.lower, (*path, 0), bound)
            visit(node.upper, (*path, 1), bound)
            binding = _ScopeBinding(node.index, path, node.lower, node.upper)
            visit(node.body, (*path, 2), (*bound, binding))
            return
        for index, child in enumerate(expression_children(node)):
            visit(child, (*path, index), bound)

    visit(expression, (), ())
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
    result: set[str] = set()
    for child in expression_children(expression):
        result.update(_free_symbols(child, bound))
    return result


def _optimization_report(  # pyright: ignore[reportUnusedFunction]
    request: AnalysisRequest, expression: Expression | None
) -> OptimizationReport:
    """Build a deliberately small, independently checked local-advice report.

    The retained expression is never replaced: this optional pass only recognizes
    identity neutral operations whose direct operation tally is strictly lower.
    Unsupported shapes intentionally yield a completed empty report.
    """
    from py_science.formula.analyzer import count_operations
    from py_science.formula.expressions import BinaryOperator, IntegerLiteral
    from py_science.formula.models import (
        IdentityEvidence,
        OptimizationOccurrence,
        OptimizationSuggestion,
        OptimizationTarget,
    )

    limit = request.optimization.max_suggestions  # type: ignore[attr-defined]
    if limit == 0:
        return OptimizationReport(requested_limit=0, status="disabled")
    if expression is None or not isinstance(expression, BinaryExpression):
        return OptimizationReport(requested_limit=limit, status="complete")
    replacement: Expression | None = None
    kind = "redundant_operation_removal"
    right_neutral = isinstance(expression.right, IntegerLiteral) and (
        (
            expression.right.value == 0
            and expression.operator in {BinaryOperator.ADD, BinaryOperator.SUBTRACT}
        )
        or (
            expression.right.value == 1
            and expression.operator in {BinaryOperator.MULTIPLY, BinaryOperator.DIVIDE}
        )
    )
    left_neutral = isinstance(expression.left, IntegerLiteral) and (
        (expression.left.value == 0 and expression.operator is BinaryOperator.ADD)
        or (expression.left.value == 1 and expression.operator is BinaryOperator.MULTIPLY)
    )
    if right_neutral:
        replacement = expression.left
    elif left_neutral:
        replacement = expression.right
    if replacement is None:
        return OptimizationReport(requested_limit=limit, status="complete")
    try:
        original = render(expression)
        proposed = render(replacement)
    except NormalizationError:
        return OptimizationReport(
            requested_limit=limit,
            status="incomplete",
            qualifications=("optimization rendering budget exhausted",),
        )
    before, after = count_operations(expression).total, count_operations(replacement).total
    if after >= before:
        return OptimizationReport(requested_limit=limit, status="complete")
    from py_science.formula.models import Interpretation

    suggestion = OptimizationSuggestion(
        kind=kind,
        target=OptimizationTarget(kind="expression"),
        occurrences=(OptimizationOccurrence(path=()),),
        original=Interpretation(normalized_sympy=original.sympy, normalized_latex=original.latex),
        proposed=Interpretation(normalized_sympy=proposed.sympy, normalized_latex=proposed.latex),
        conclusion="proved",
        evidence=IdentityEvidence(
            statement="exact symbolic identity checked for neutral operation"
        ),
        work_before=str(before),
        work_after=str(after),
        savings=str(before - after),
    )
    return OptimizationReport(requested_limit=limit, status="complete", suggestions=(suggestion,))
