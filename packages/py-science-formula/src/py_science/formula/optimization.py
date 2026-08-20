"""Private bounded local optimization generation and verification."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key
from typing import Literal

from py_science.formula.computation import RetainedComputation, RetainedWorkAnalysis
from py_science.formula.equivalence import equivalence_answer
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    IntegerLiteral,
    Relationship,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
)
from py_science.formula.mapped_outputs import ExpansionBudget, MappedOutputExpander
from py_science.formula.models import (
    AnalysisRequest,
    IdentityEvidence,
    Interpretation,
    OptimizationIntermediate,
    OptimizationOccurrence,
    OptimizationReport,
    OptimizationSuggestion,
    OptimizationTarget,
    RelationshipUse,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import (
    NormalizationError,
    bounded_factor_candidate,
    render,
)
from py_science.formula.work import (
    AggregateWorkComparisonInput,
    WorkAnalysis,
    WorkContext,
    WorkRenderBudget,
    aggregate_analysis,
    analyze_work,
    compare_aggregate_work,
    exact_work_sign,
    render_work,
)

MAX_OPTIMIZATION_INSPECTIONS = 16_384
MAX_OPTIMIZATION_CANDIDATES = 256
MAX_OPTIMIZATION_TRANSFORM_NODES = 8_192
MAX_OPTIMIZATION_PROOFS = 256


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
    ]
    target: str
    original: Expression
    proposed: Expression
    occurrences: tuple[_Occurrence, ...]
    intermediate_name: str | None = None
    intermediate_expression: Expression | None = None
    intermediate_scope: _EvaluationScope | None = None


@dataclass(frozen=True, slots=True)
class _Accepted:
    suggestion: OptimizationSuggestion


@dataclass(frozen=True, slots=True)
class _Rejected:
    reason: str


@dataclass(frozen=True, slots=True)
class _Exhausted:
    reason: str


type _CandidateOutcome = _Accepted | _Rejected | _Exhausted


@dataclass(slots=True)
class _OptimizationBudget:
    inspections: int = 0
    candidates: int = 0
    proofs: int = 0

    def inspect(self, amount: int = 1) -> None:
        self.inspections += amount
        if self.inspections > MAX_OPTIMIZATION_INSPECTIONS:
            raise _TraversalExhausted("optimization inspection budget exhausted")

    def candidate(self) -> bool:
        if self.candidates >= MAX_OPTIMIZATION_CANDIDATES:
            return False
        self.candidates += 1
        return True

    def proof(self) -> None:
        self.proofs += 1
        if self.proofs > MAX_OPTIMIZATION_PROOFS:
            raise _TraversalExhausted("optimization proof budget exhausted")


class _TraversalExhausted(RuntimeError):
    pass


def _detect_occurrences(
    target: str,
    expression: Expression,
    producers: Mapping[str, object],
    *,
    output_indices: tuple[str, ...] = (),
    output_domains: Mapping[str, tuple[Expression, Expression]] | None = None,
    max_nodes: int = MAX_OPTIMIZATION_INSPECTIONS,
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
                        _free_symbols(node, frozenset((*output_indices, *binder_names)))
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


def _all_symbol_names(expression: Expression) -> set[str]:
    result: set[str] = set()
    if isinstance(expression, (Symbol, IndexedValue, Call)):
        result.add(expression.name)
    if isinstance(expression, Sum):
        result.add(expression.index)
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
        return node

    return visit(expression, ())


def _smallest_scope(expression: Expression, scope: _EvaluationScope) -> _EvaluationScope:
    raw = _free_symbols(expression)
    binders = tuple(binding for binding in scope.binders if binding.name in raw)
    outputs = tuple(binding for binding in scope.output_bindings if binding.name in raw)
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


def _generate_candidates(
    computed: RetainedComputation, budget: _OptimizationBudget
) -> tuple[tuple[_CandidateComputation, ...], str | None]:
    candidates: list[_CandidateComputation] = []
    generated_name = _generated_name(computed)
    for target, expression, output_indices, output_domains in _target_inputs(computed):
        try:
            occurrences = _detect_occurrences(
                target,
                expression,
                computed.producers,
                output_indices=output_indices,
                output_domains=output_domains,
                max_nodes=max(1, MAX_OPTIMIZATION_INSPECTIONS - budget.inspections),
            )
            budget.inspect(max(1, expression_node_count(expression)))
        except _TraversalExhausted as error:
            return tuple(candidates), str(error)

        grouped: dict[tuple[Expression, _EvaluationScope], list[_Occurrence]] = defaultdict(list)
        for occurrence in occurrences:
            if not isinstance(occurrence.expression, Sum):
                grouped[(occurrence.expression, occurrence.scope)].append(occurrence)
        for (repeated, scope), items in grouped.items():
            if len(items) < 2 or expression_node_count(repeated) < 2:
                continue
            if not budget.candidate():
                return tuple(candidates), "optimization candidate budget exhausted"
            kind: Literal["repeated_subexpression", "repeated_call", "reciprocal_reuse"]
            if (
                isinstance(repeated, BinaryExpression)
                and repeated.operator is BinaryOperator.DIVIDE
                and isinstance(repeated.left, IntegerLiteral)
                and repeated.left.value == 1
            ):
                kind = "reciprocal_reuse"
            elif isinstance(repeated, Call):
                kind = "repeated_call"
            else:
                kind = "repeated_subexpression"
            proposed = _replace_paths(
                expression, (item.path for item in items), Symbol(generated_name)
            )
            candidates.append(
                _CandidateComputation(
                    kind=kind,
                    target=target,
                    original=expression,
                    proposed=proposed,
                    occurrences=tuple(items),
                    intermediate_name=generated_name,
                    intermediate_expression=repeated,
                    intermediate_scope=_smallest_scope(repeated, scope),
                )
            )

        for occurrence in occurrences:
            node = occurrence.expression
            replacement = _neutral_replacement(node)
            if replacement is not None:
                if not budget.candidate():
                    return tuple(candidates), "optimization candidate budget exhausted"
                candidates.append(
                    _CandidateComputation(
                        kind="redundant_operation_removal",
                        target=target,
                        original=expression,
                        proposed=_replace_paths(expression, (occurrence.path,), replacement),
                        occurrences=(occurrence,),
                    )
                )
            factored = _factored(node)
            if factored is not None:
                if not budget.candidate():
                    return tuple(candidates), "optimization candidate budget exhausted"
                candidates.append(
                    _CandidateComputation(
                        kind="factoring",
                        target=target,
                        original=expression,
                        proposed=_replace_paths(expression, (occurrence.path,), factored),
                        occurrences=(occurrence,),
                    )
                )
            # A body subtree independent of the innermost active iterator can be
            # evaluated immediately outside that iterator. Bounds stay outside it.
            if occurrence.scope.binders:
                binding = occurrence.scope.binders[-1]
                raw_symbols = _free_symbols(node)
                useful = (
                    isinstance(node, (BinaryExpression, Call)) and expression_node_count(node) > 1
                )
                if (
                    useful
                    and binding.name not in raw_symbols
                    and occurrence.path[: len(binding.path) + 1] == (*binding.path, 2)
                ):
                    if not budget.candidate():
                        return tuple(candidates), "optimization candidate budget exhausted"
                    outer_scope = _EvaluationScope(
                        occurrence.scope.output_indices,
                        occurrence.scope.output_bindings,
                        occurrence.scope.binders[:-1],
                    )
                    candidates.append(
                        _CandidateComputation(
                            kind="iterator_invariant_hoisting",
                            target=target,
                            original=expression,
                            proposed=_replace_paths(
                                expression, (occurrence.path,), Symbol(generated_name)
                            ),
                            occurrences=(occurrence,),
                            intermediate_name=generated_name,
                            intermediate_expression=node,
                            intermediate_scope=_smallest_scope(node, outer_scope),
                        )
                    )
    return tuple(candidates), None


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


def _as_work(analysis: RetainedWorkAnalysis) -> WorkAnalysis:
    return WorkAnalysis(
        operations=analysis.operations,
        opaque_work=analysis.opaque_work,
        invocations=dict(analysis.invocations),
        unknown_costs=set(analysis.unknown_costs),
        unresolved=set(analysis.unresolved),
        direct_work_blockers=set(analysis.direct_work_blockers),
    )


def _aggregate_scope(
    analysis: WorkAnalysis, scope: _EvaluationScope, context: WorkContext
) -> WorkAnalysis | None:
    scoped = WorkContext(
        definitions=context.definitions,
        primitives=context.primitives,
        variable_domains=context.variable_domains,
        integer_symbols=frozenset(
            (
                *context.integer_symbols,
                *scope.output_indices,
                *(item.name for item in scope.binders),
            )
        ),
        nonnegative_symbols=context.nonnegative_symbols,
        call_stack=context.call_stack,
    )
    result = analysis
    for binding in reversed(scope.binders):
        if binding.lower is None or binding.upper is None:
            return None
        result, unresolved = aggregate_analysis(
            result,
            binding.name,
            binding.lower,
            binding.upper,
            scoped,
            f"optimization intermediate binder {binding.name}",
        )
        if unresolved is not None:
            result.unresolved.add(unresolved)
    for binding in reversed(scope.output_bindings):
        if binding.lower is None or binding.upper is None:
            return None
        result, unresolved = aggregate_analysis(
            result,
            binding.name,
            binding.lower,
            binding.upper,
            scoped,
            f"optimization intermediate output {binding.name}",
        )
        if unresolved is not None:
            result.unresolved.add(unresolved)
    return result


def _candidate_target_work(
    candidate: _CandidateComputation,
    computed: RetainedComputation,
    context: WorkContext,
) -> WorkAnalysis | None:
    equation = next((item for item in computed.equations if item.name == candidate.target), None)
    indices = equation.domain_order if equation is not None else ()
    scoped = WorkContext(
        definitions=context.definitions,
        primitives=context.primitives,
        variable_domains=context.variable_domains,
        integer_symbols=context.integer_symbols | frozenset(indices),
        nonnegative_symbols=context.nonnegative_symbols,
        call_stack=context.call_stack,
    )
    result = analyze_work(candidate.proposed, scoped)
    if equation is not None:
        by_index = {item.index: item for item in equation.output_domains}
        for index in reversed(equation.domain_order):
            domain = by_index[index]
            result, unresolved = aggregate_analysis(
                result,
                index,
                domain.lower,
                domain.upper,
                scoped,
                f"optimization equation {candidate.target} output index {index}",
            )
            if unresolved is not None:
                result.unresolved.add(unresolved)
    if candidate.intermediate_expression is not None:
        assert candidate.intermediate_scope is not None
        intermediate = _aggregate_scope(
            analyze_work(candidate.intermediate_expression, scoped),
            candidate.intermediate_scope,
            scoped,
        )
        if intermediate is None:
            return None
        result = result.combine(intermediate)
    return result


def _whole_candidate_work(
    candidate: _CandidateComputation,
    computed: RetainedComputation,
    context: WorkContext,
) -> WorkAnalysis | None:
    changed = _candidate_target_work(candidate, computed, context)
    if changed is None:
        return None
    if computed.expression is not None:
        return changed
    result = WorkAnalysis()
    for name in computed.dependency_order:
        result = result.combine(
            changed if name == candidate.target else _as_work(computed.equation_analyses[name])
        )
    return result


def _reasoning(request: AnalysisRequest, computed: RetainedComputation) -> ReasoningContext | None:
    try:
        return ReasoningContext.build(
            {name: item.domain for name, item in request.variables.items()},
            computed.knowledge.definitions,
            computed.knowledge.assumptions,
        )
    except ExpressionTooComplex:
        return None


def _unique_uses(values: Iterable[RelationshipUse]) -> tuple[RelationshipUse, ...]:
    result: list[RelationshipUse] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _interpretation(expression: Expression) -> Interpretation:
    rendered = render(expression)
    return Interpretation(normalized_sympy=rendered.sympy, normalized_latex=rendered.latex)


def _verify_candidate(
    candidate: _CandidateComputation,
    request: AnalysisRequest,
    computed: RetainedComputation,
    context: WorkContext,
    reasoning: ReasoningContext | None,
    budget: _OptimizationBudget,
) -> _CandidateOutcome:
    if expression_node_count(candidate.proposed) > MAX_OPTIMIZATION_TRANSFORM_NODES:
        return _Exhausted("optimization transformation budget exhausted")
    expansion_budget = ExpansionBudget(remaining=MAX_OPTIMIZATION_TRANSFORM_NODES)
    reserved: set[str] = set()
    for _target, expression, _indices, _domains in _target_inputs(computed):
        reserved.update(_all_symbol_names(expression))
    try:
        original_expanded = MappedOutputExpander(computed, expansion_budget, set(reserved)).expand(
            candidate.original
        )
        expanded = MappedOutputExpander(computed, expansion_budget, set(reserved)).expand(
            candidate.proposed,
            {candidate.intermediate_name: candidate.intermediate_expression}
            if candidate.intermediate_name is not None
            and candidate.intermediate_expression is not None
            else None,
        )
    except ExpressionTooComplex:
        return _Exhausted("optimization substitution budget exhausted")
    budget.proof()
    answer = equivalence_answer(original_expanded, expanded, reasoning)
    if (
        answer.conclusion not in {"proved", "proved_under_assumptions"}
        and original_expanded == expanded
    ):
        from py_science.formula.models import QueryAnswer

        answer = QueryAnswer(
            conclusion="proved",
            evidence=IdentityEvidence(
                statement="checked intermediate substitution reconstructs the retained output"
            ),
        )
    if answer.conclusion not in {"proved", "proved_under_assumptions"}:
        return _Rejected("candidate output equivalence is not proved")
    if not isinstance(answer.evidence, IdentityEvidence):
        return _Rejected("candidate proof has no exact identity evidence")

    after = _whole_candidate_work(candidate, computed, context)
    before = _as_work(computed.aggregate_analysis)
    if after is None:
        return _Rejected("candidate scope multiplicity is unavailable")
    if after.unknown_costs or after.unresolved or after.direct_work_blockers:
        return _Rejected("candidate aggregate work is unavailable")
    if before.unknown_costs or before.unresolved or before.direct_work_blockers:
        return _Rejected("retained aggregate work is unavailable")
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(
            work=after.total_work,
            unknown_costs=frozenset(after.unknown_costs),
            direct_work_blockers=frozenset(after.direct_work_blockers),
        ),
        AggregateWorkComparisonInput(
            work=before.total_work,
            unknown_costs=frozenset(before.unknown_costs),
            direct_work_blockers=frozenset(before.direct_work_blockers),
        ),
        reasoning,
        semantic_established=True,
    )
    if relation.status != "first_lower" or relation.delta is None:
        return _Rejected("candidate has no proved positive aggregate-work reduction")
    if exact_work_sign(before.total_work) in {-1, 0} or exact_work_sign(after.total_work) in {
        -1,
        0,
    }:
        return _Rejected("candidate before and after work must both be positive")

    work_budget = WorkRenderBudget()
    try:
        work_before = render_work(before.total_work, work_budget)
        work_after = render_work(after.total_work, work_budget)
        savings = render_work(relation.delta, work_budget)
        original = _interpretation(candidate.original)
        proposed = _interpretation(candidate.proposed)
        intermediate = (
            OptimizationIntermediate(
                name=candidate.intermediate_name,
                expression=_interpretation(candidate.intermediate_expression),
                scope_binders=tuple(item.name for item in candidate.intermediate_scope.binders),
                scope_output_indices=candidate.intermediate_scope.output_indices,
            )
            if candidate.intermediate_name is not None
            and candidate.intermediate_expression is not None
            and candidate.intermediate_scope is not None
            else None
        )
    except (ExpressionTooComplex, NormalizationError):
        return _Exhausted("optimization rendering budget exhausted")

    conditions = tuple(dict.fromkeys((*answer.conditions, *relation.conditions)))
    assumptions = _unique_uses((*answer.assumptions_used, *relation.assumptions_used))
    conclusion: Literal["proved", "proved_under_assumptions"] = (
        "proved_under_assumptions" if conditions or assumptions else "proved"
    )
    target = (
        OptimizationTarget(kind="expression")
        if candidate.target == "expression" and computed.expression is not None
        else OptimizationTarget(kind="equation", name=candidate.target)
    )
    suggestion = OptimizationSuggestion(
        kind=candidate.kind,
        target=target,
        occurrences=tuple(
            OptimizationOccurrence(
                path=item.path,
                binders=item.binders,
                output_indices=item.scope.output_indices,
            )
            for item in candidate.occurrences
        ),
        original=original,
        proposed=proposed,
        intermediate=intermediate,
        conclusion=conclusion,
        evidence=answer.evidence,
        conditions=conditions,
        assumptions_used=assumptions,
        work_before=work_before,
        work_after=work_after,
        savings=savings,
    )
    return _Accepted(suggestion)


def _suggestion_order(left: OptimizationSuggestion, right: OptimizationSuggestion) -> int:
    if (left.conclusion == "proved") != (right.conclusion == "proved"):
        return -1 if left.conclusion == "proved" else 1
    try:
        left_savings = Fraction(left.savings)
        right_savings = Fraction(right.savings)
    except (ValueError, ZeroDivisionError):
        left_savings = right_savings = None
    if left_savings is not None and right_savings is not None and left_savings != right_savings:
        return -1 if left_savings > right_savings else 1
    left_key = (
        left.target.name or "",
        left.kind,
        left.occurrences[0].path,
        left.proposed.normalized_sympy,
    )
    right_key = (
        right.target.name or "",
        right.kind,
        right.occurrences[0].path,
        right.proposed.normalized_sympy,
    )
    return (left_key > right_key) - (left_key < right_key)


def _optimization_report(  # pyright: ignore[reportUnusedFunction]
    request: AnalysisRequest, computed: RetainedComputation, context: WorkContext
) -> OptimizationReport:
    """Generate bounded candidates and publish only common-verifier acceptances."""
    limit = request.optimization.max_suggestions
    if limit == 0:
        return OptimizationReport(requested_limit=0, status="disabled")
    budget = _OptimizationBudget()
    accepted: list[OptimizationSuggestion] = []
    qualifications: list[str] = []
    try:
        candidates, generation_exhaustion = _generate_candidates(computed, budget)
        if generation_exhaustion is not None:
            qualifications.append(generation_exhaustion)
        reasoning = _reasoning(request, computed)
        if reasoning is None:
            return OptimizationReport(
                requested_limit=limit,
                status="incomplete",
                qualifications=("optimization proof budget exhausted",),
            )
        seen: set[tuple[str, str, str]] = set()
        for candidate in candidates:
            outcome = _verify_candidate(candidate, request, computed, context, reasoning, budget)
            if isinstance(outcome, _Exhausted):
                qualifications.append(outcome.reason)
                continue
            if isinstance(outcome, _Rejected):
                continue
            suggestion = outcome.suggestion
            key = (
                suggestion.target.name or "expression",
                suggestion.proposed.normalized_sympy,
                suggestion.intermediate.expression.normalized_sympy
                if suggestion.intermediate is not None
                else "",
            )
            if key not in seen:
                seen.add(key)
                accepted.append(suggestion)
    except _TraversalExhausted as error:
        qualifications.append(str(error))
    except (ExpressionTooComplex, NormalizationError):
        qualifications.append("optimization search budget exhausted")

    accepted.sort(key=cmp_to_key(_suggestion_order))
    return OptimizationReport(
        requested_limit=limit,
        status="incomplete" if qualifications else "complete",
        suggestions=tuple(accepted[:limit]),
        qualifications=tuple(dict.fromkeys(qualifications)),
    )
