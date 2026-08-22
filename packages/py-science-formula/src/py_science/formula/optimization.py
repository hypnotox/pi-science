"""Private bounded local optimization generation and verification."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cmp_to_key
from itertools import permutations
from typing import Literal

from py_science.formula.computation import RetainedComputation, RetainedWorkAnalysis
from py_science.formula.domains import OutputDomain
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
    Let,
    Relationship,
    RelationshipOperator,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
    substitute,
)
from py_science.formula.mapped_outputs import (
    ExpansionBudget,
    MappedOutputExpander,
)
from py_science.formula.models import (
    AnalysisFailure,
    AnalysisRequest,
    EquationRequest,
    IdentityEvidence,
    Interpretation,
    OptimizationCandidate,
    OptimizationIntermediate,
    OptimizationKind,
    OptimizationOccurrence,
    OptimizationOrdering,
    OptimizationPlan,
    OptimizationReport,
    OptimizationSuggestion,
    OptimizationTarget,
    OptimizationTraceStep,
    OptimizationTransformation,
    QueryAnswer,
    RelationshipUse,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import (
    BoundedHornerCandidate,
    BoundedHornerRefusal,
    NormalizationError,
    bounded_factor_candidate,
    bounded_horner_candidate,
    render,
)
from py_science.formula.work import (
    AggregateWorkComparisonInput,
    WorkAnalysis,
    WorkContext,
    WorkRenderBudget,
    aggregate_analysis,
    aggregate_output_analysis,
    analyze_work,
    compare_aggregate_work,
    exact_work_sign,
    project_optimization_objective,
    render_work,
    substitute_analysis,
)
from pydantic import ValidationError

MAX_OPTIMIZATION_INSPECTIONS = 16_384
MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS = 131_072
MAX_OPTIMIZATION_WHOLE_INSPECTIONS = 147_456
MAX_OPTIMIZATION_CANDIDATES = 256
MAX_OPTIMIZATION_COMPLETE_REANALYSES = 8
MAX_OPTIMIZATION_EXPANDED_PARENTS = 8
MAX_OPTIMIZATION_RETAINED_STATES = 8
MAX_OPTIMIZATION_TRANSFORM_NODES = 8_192
MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES = 32_768
MAX_OPTIMIZATION_PROOFS = 256
MAX_OPTIMIZATION_PROOF_NODES = 32_768
MAX_OPTIMIZATION_WORK_NODES = 32_768
MAX_OPTIMIZATION_WHOLE_PROOFS = 512
MAX_OPTIMIZATION_WHOLE_PROOF_NODES = 65_536
MAX_OPTIMIZATION_WHOLE_WORK_NODES = 65_536
MAX_OPTIMIZATION_FINAL_STATES = 16
MAX_OPTIMIZATION_FINAL_PROOFS = 16
MAX_OPTIMIZATION_FINAL_PROOF_NODES = 32_768
MAX_OPTIMIZATION_FINAL_WORK_NODES = 32_768
MAX_HORNER_TARGET_NODES = 512
MAX_HORNER_VARIABLES = 1
MAX_HORNER_DEGREE = 8
MAX_HORNER_TERMS = 64
MAX_HORNER_GENERATED_NODES = 512


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


@dataclass(frozen=True, slots=True)
class _Accepted:
    suggestion: OptimizationSuggestion
    candidate: AnalysisRequest
    savings_expression: Expression
    computed: RetainedComputation | None = None
    trace: tuple[tuple[OptimizationSuggestion, AnalysisRequest], ...] = ()


@dataclass(frozen=True, slots=True)
class _SearchState:
    """One verified complete computation in the bounded canonical frontier."""

    request: AnalysisRequest
    computed: RetainedComputation
    objective_total: Expression
    canonical_key: tuple[object, ...]
    depth: int
    generated_names: tuple[str, ...]
    trace: tuple[tuple[OptimizationSuggestion, AnalysisRequest], ...]
    concrete_identity: str
    local_savings: Expression


@dataclass(frozen=True, slots=True)
class _Rejected:
    reason: str


@dataclass(frozen=True, slots=True)
class _Exhausted:
    reason: str


type _CandidateOutcome = _Accepted | _Rejected | _Exhausted


@dataclass(frozen=True, slots=True)
class _OptimizationBudgetConfig:
    """Private test seam for every fixed composed-search allowance."""

    inspections: int = MAX_OPTIMIZATION_INSPECTIONS
    depth_two_inspections: int = MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS
    whole_inspections: int = MAX_OPTIMIZATION_WHOLE_INSPECTIONS
    candidates: int = MAX_OPTIMIZATION_CANDIDATES
    complete_reanalyses: int = MAX_OPTIMIZATION_COMPLETE_REANALYSES
    expanded_parents: int = MAX_OPTIMIZATION_EXPANDED_PARENTS
    retained_states: int = MAX_OPTIMIZATION_RETAINED_STATES
    aggregate_transform_nodes: int = MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES
    proofs: int = MAX_OPTIMIZATION_PROOFS
    proof_nodes: int = MAX_OPTIMIZATION_PROOF_NODES
    work_nodes: int = MAX_OPTIMIZATION_WORK_NODES
    whole_proofs: int = MAX_OPTIMIZATION_WHOLE_PROOFS
    whole_proof_nodes: int = MAX_OPTIMIZATION_WHOLE_PROOF_NODES
    whole_work_nodes: int = MAX_OPTIMIZATION_WHOLE_WORK_NODES
    final_states: int = MAX_OPTIMIZATION_FINAL_STATES
    final_proofs: int = MAX_OPTIMIZATION_FINAL_PROOFS
    final_proof_nodes: int = MAX_OPTIMIZATION_FINAL_PROOF_NODES
    final_work_nodes: int = MAX_OPTIMIZATION_FINAL_WORK_NODES


def _default_budget_config() -> _OptimizationBudgetConfig:
    """Read module limits at request time so monkeypatched private seams remain useful."""
    return _OptimizationBudgetConfig(
        inspections=MAX_OPTIMIZATION_INSPECTIONS,
        depth_two_inspections=MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS,
        whole_inspections=MAX_OPTIMIZATION_WHOLE_INSPECTIONS,
        candidates=MAX_OPTIMIZATION_CANDIDATES,
        complete_reanalyses=MAX_OPTIMIZATION_COMPLETE_REANALYSES,
        expanded_parents=MAX_OPTIMIZATION_EXPANDED_PARENTS,
        retained_states=MAX_OPTIMIZATION_RETAINED_STATES,
        aggregate_transform_nodes=MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES,
        proofs=MAX_OPTIMIZATION_PROOFS,
        proof_nodes=MAX_OPTIMIZATION_PROOF_NODES,
        work_nodes=MAX_OPTIMIZATION_WORK_NODES,
        whole_proofs=MAX_OPTIMIZATION_WHOLE_PROOFS,
        whole_proof_nodes=MAX_OPTIMIZATION_WHOLE_PROOF_NODES,
        whole_work_nodes=MAX_OPTIMIZATION_WHOLE_WORK_NODES,
        final_states=MAX_OPTIMIZATION_FINAL_STATES,
        final_proofs=MAX_OPTIMIZATION_FINAL_PROOFS,
        final_proof_nodes=MAX_OPTIMIZATION_FINAL_PROOF_NODES,
        final_work_nodes=MAX_OPTIMIZATION_FINAL_WORK_NODES,
    )


@dataclass(slots=True)
class _WholeTransitionBudget:
    """Whole-request transition ceilings shared by both search depths."""

    config: _OptimizationBudgetConfig
    inspections: int = 0
    proofs: int = 0
    proof_nodes: int = 0
    work_nodes: int = 0

    @staticmethod
    def _accept(resource: str, measured: int, configured: int) -> None:
        if measured > configured:
            raise _BudgetExhausted(resource, measured, configured)

    def inspect(self, amount: int) -> None:
        self.inspections += amount
        self._accept(
            "whole-request inspected nodes", self.inspections, self.config.whole_inspections
        )

    def proof(self, nodes: int) -> None:
        self.proofs += 1
        self._accept("whole-request proof steps", self.proofs, self.config.whole_proofs)
        self.proof_nodes += nodes
        self._accept("whole-request proof nodes", self.proof_nodes, self.config.whole_proof_nodes)

    def work(self, nodes: int) -> None:
        self.work_nodes += nodes
        self._accept(
            "whole-request work-comparison nodes",
            self.work_nodes,
            self.config.whole_work_nodes,
        )


@dataclass(slots=True)
class _OptimizationBudget:
    config: _OptimizationBudgetConfig = _OptimizationBudgetConfig()
    label: str = "transition"
    whole: _WholeTransitionBudget | None = None
    inspections: int = 0
    candidates: int = 0
    complete_reanalyses: int = 0
    expanded_parents: int = 0
    retained_states: int = 0
    aggregate_transform_nodes: int = 0
    proofs: int = 0
    proof_nodes: int = 0
    work_nodes: int = 0

    def resource(self, resource: str) -> str:
        return f"{self.label} {resource}" if self.label else resource

    @staticmethod
    def _accept(resource: str, measured: int, configured: int) -> None:
        if measured > configured:
            raise _BudgetExhausted(resource, measured, configured)

    def inspect(self, amount: int = 1) -> None:
        measured = self.inspections + amount
        self._accept(self.resource("inspected nodes"), measured, self.config.inspections)
        if self.whole is not None:
            self.whole.inspect(amount)
        self.inspections = measured

    def candidate(self) -> None:
        measured = self.candidates + 1
        self._accept(self.resource("generated transitions"), measured, self.config.candidates)
        self.candidates = measured

    def reanalysis(self) -> None:
        measured = self.complete_reanalyses + 1
        self._accept(
            self.resource("complete candidate reanalyses"),
            measured,
            self.config.complete_reanalyses,
        )
        self.complete_reanalyses = measured

    def parent(self) -> None:
        measured = self.expanded_parents + 1
        self._accept(self.resource("expanded parents"), measured, self.config.expanded_parents)
        self.expanded_parents = measured

    def retain(self) -> None:
        measured = self.retained_states + 1
        self._accept(self.resource("retained states"), measured, self.config.retained_states)
        self.retained_states = measured

    def transformation(self, nodes: int) -> None:
        self._accept("per-candidate transformation nodes", nodes, MAX_OPTIMIZATION_TRANSFORM_NODES)
        measured = self.aggregate_transform_nodes + nodes
        self._accept(
            self.resource("aggregate transformation nodes"),
            measured,
            self.config.aggregate_transform_nodes,
        )
        self.aggregate_transform_nodes = measured

    def proof(self, nodes: int) -> None:
        measured = self.proofs + 1
        self._accept(self.resource("proof steps"), measured, self.config.proofs)
        measured_nodes = self.proof_nodes + nodes
        self._accept(self.resource("proof nodes"), measured_nodes, self.config.proof_nodes)
        if self.whole is not None:
            self.whole.proof(nodes)
        self.proofs = measured
        self.proof_nodes = measured_nodes

    def work(self, nodes: int) -> None:
        measured = self.work_nodes + nodes
        self._accept(self.resource("work-comparison nodes"), measured, self.config.work_nodes)
        if self.whole is not None:
            self.whole.work(nodes)
        self.work_nodes = measured


class _BudgetExhausted(RuntimeError):
    def __init__(self, resource: str, measured: int, configured: int) -> None:
        self.resource = resource
        self.measured = measured
        self.configured = configured
        super().__init__(
            f"optimization {resource} budget exhausted "
            f"(measured {measured}, configured {configured})"
        )


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


def _complete_candidate(
    candidate: _CandidateComputation,
    request: AnalysisRequest,
    computed: RetainedComputation,
) -> AnalysisRequest:
    """Build the authoritative, reparseable computation for one local proposal."""
    intermediate_name = candidate.intermediate_name
    intermediate_expression = candidate.intermediate_expression
    intermediate_scope = candidate.intermediate_scope
    if intermediate_expression is not None:
        assert intermediate_name is not None and intermediate_scope is not None
    transformations = dict(
        (target, proposed)
        for target, _original, proposed in (
            candidate.transformed_targets
            or ((candidate.target, candidate.original, candidate.proposed),)
        )
    )
    if computed.expression is not None:
        expression = transformations["expression"]
        if candidate.intermediate_expression is not None:
            expression = _wrap_complete_let(expression, candidate)
        complete = request.model_copy(
            update={"expression": render(expression).sympy, "queries": (), "scenarios": ()}
        )
        return AnalysisRequest.model_validate(complete.model_dump(mode="python"))

    equations: list[EquationRequest] = []
    for source in request.equations:
        parsed = next(item for item in computed.equations if item.name == source.name)
        right = transformations.get(source.name, parsed.formula.right)
        if (
            source.name == candidate.target
            and intermediate_expression is not None
            and intermediate_scope is not None
            and intermediate_scope.binders
        ):
            right = _wrap_complete_let(right, candidate)
        equation = render(Equation(parsed.formula.left, right)).sympy
        equations.append(source.model_copy(update={"expression": equation}))
    if (
        intermediate_expression is not None
        and intermediate_scope is not None
        and not intermediate_scope.binders
    ):
        assert intermediate_name is not None
        indices = intermediate_scope.output_indices
        target = next(item for item in request.equations if item.name == candidate.target)
        left: Expression = (
            IndexedValue(intermediate_name, tuple(Symbol(name) for name in indices))
            if indices
            else Symbol(intermediate_name)
        )
        equations.append(
            EquationRequest(
                name=intermediate_name,
                expression=render(Equation(left, intermediate_expression)).sympy,
                domains={name: target.domains[name] for name in indices},
                constraints=tuple(
                    constraint for constraint in target.constraints if constraint.target in indices
                ),
            )
        )
    complete = request.model_copy(
        update={"expression": None, "equations": tuple(equations), "queries": (), "scenarios": ()}
    )
    return AnalysisRequest.model_validate(complete.model_dump(mode="python"))


_FAMILY_ORDER: tuple[OptimizationKind, ...] = (
    "repeated_subexpression",
    "repeated_call",
    "reciprocal_reuse",
    "factoring",
    "redundant_operation_removal",
    "iterator_invariant_hoisting",
    "cross_equation_sharing",
    "horner",
)


class _RetainedLaneCollector:
    """Retain the canonical round-robin prefix without materializing all proposals."""

    def __init__(self, budget: _OptimizationBudget) -> None:
        self.budget = budget
        self._capacity = max(0, budget.config.candidates - budget.candidates)
        self._counts: dict[tuple[object, ...], int] = {}
        self._retained: dict[tuple[object, ...], list[_CandidateDescriptor]] = {}
        self._more_proposals = False

    @property
    def retained_count(self) -> int:
        return sum(map(len, self._retained.values()))

    def _quotas(self) -> dict[tuple[object, ...], int]:
        quotas = {key: 0 for key in self._counts}
        active = [(key, 0) for key in sorted(self._counts) if self._counts[key]]
        remaining = self._capacity
        while active and remaining:
            following: list[tuple[tuple[object, ...], int]] = []
            for key, position in active:
                quotas[key] += 1
                remaining -= 1
                position += 1
                if position < self._counts[key]:
                    following.append((key, position))
                if not remaining:
                    break
            active = following
        return quotas

    def add(self, lane: tuple[object, ...], descriptor: _CandidateDescriptor) -> None:
        """Retain descriptor recipes for the canonical fair prefix.

        Discovery never materializes a transition.  Once every lane has been
        observed, the scheduler chooses its stable round-robin prefix and is
        the sole owner of both the transition charge and factory invocation.
        """
        self._counts[lane] = self._counts.get(lane, 0) + 1
        self._more_proposals |= sum(self._counts.values()) > self._capacity
        quotas = self._quotas()
        for key, values in self._retained.items():
            del values[quotas[key] :]
        values = self._retained.setdefault(lane, [])
        quota = quotas[lane]
        if quota:
            values.append(descriptor)
            values.sort(key=lambda item: item.sort_key)
            del values[quota:]
        assert self.retained_count <= self._capacity

    def lanes_for(
        self, lane_prefix: tuple[object, ...]
    ) -> dict[OptimizationKind, tuple[_CandidateDescriptor, ...]]:
        return {kind: tuple(self._retained.get((*lane_prefix, kind), ())) for kind in _FAMILY_ORDER}

    def schedule(self) -> tuple[tuple[tuple[object, ...], _CandidateComputation], ...]:
        selected = _round_robin_descriptors(
            (key, tuple(values)) for key, values in self._retained.items()
        )
        materialized: list[tuple[tuple[object, ...], _CandidateComputation]] = []
        for lane, descriptor in selected:
            self.budget.candidate()
            materialized.append((lane, descriptor.factory()))
        return tuple(materialized)

    def exhaustion(self) -> str | None:
        if not self._more_proposals:
            return None
        return str(
            _BudgetExhausted(
                self.budget.resource("generated transitions"),
                self._capacity + 1,
                self.budget.config.candidates,
            )
        )


def _generate_candidate_lanes(
    computed: RetainedComputation,
    budget: _OptimizationBudget,
    collector: _RetainedLaneCollector | None = None,
    lane_prefix: tuple[object, ...] = (),
) -> tuple[dict[OptimizationKind, tuple[_CandidateDescriptor, ...]], tuple[str, ...]]:
    """Discover lightweight recipes into a bounded, canonical shared lane collector."""
    collector = collector or _RetainedLaneCollector(budget)
    qualifications: list[str] = []
    generated_name = _generated_name(computed)
    occurrences_by_target: dict[str, tuple[_Occurrence, ...]] = {}

    def append(descriptor: _CandidateDescriptor) -> None:
        collector.add((*lane_prefix, descriptor.kind), descriptor)

    try:
        for target, expression, output_indices, output_domains in sorted(
            _target_inputs(computed), key=lambda item: item[0]
        ):
            try:
                occurrences = _detect_occurrences(
                    target,
                    expression,
                    computed.producers,
                    output_indices=output_indices,
                    output_domains=output_domains,
                    max_nodes=max(1, budget.config.inspections - budget.inspections),
                )
            except _TraversalExhausted:
                measured = budget.inspections + expression_node_count(expression)
                raise _BudgetExhausted(
                    budget.resource("inspected nodes"), measured, budget.config.inspections
                ) from None
            budget.inspect(max(1, expression_node_count(expression)))
            occurrences_by_target[target] = occurrences

            grouped: dict[tuple[Expression, _EvaluationScope], list[_Occurrence]] = defaultdict(
                list
            )
            for occurrence in occurrences:
                if not isinstance(occurrence.expression, Sum):
                    grouped[(occurrence.expression, occurrence.scope)].append(occurrence)
            for (repeated, scope), items in grouped.items():
                if len(items) < 2 or expression_node_count(repeated) < 2:
                    continue
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
                intermediate_scope = _smallest_scope(repeated, scope)
                append(
                    _generated_replacement_descriptor(
                        kind=kind,
                        target=target,
                        original=expression,
                        occurrences=tuple(items),
                        generated_name=generated_name,
                        intermediate_expression=repeated,
                        intermediate_scope=intermediate_scope,
                    )
                )

            for occurrence in occurrences:
                node = occurrence.expression
                replacement = _neutral_replacement(node)
                if replacement is not None:
                    append(
                        _replacement_descriptor(
                            kind="redundant_operation_removal",
                            target=target,
                            original=expression,
                            occurrences=(occurrence,),
                            replacement=replacement,
                        )
                    )
                factored = _factored(node)
                if factored is not None:
                    append(
                        _replacement_descriptor(
                            kind="factoring",
                            target=target,
                            original=expression,
                            occurrences=(occurrence,),
                            replacement=factored,
                        )
                    )
                budget.inspect(max(1, expression_node_count(node)))
                horner = bounded_horner_candidate(
                    node,
                    max_target_nodes=MAX_HORNER_TARGET_NODES,
                    max_polynomial_variables=MAX_HORNER_VARIABLES,
                    max_degree=MAX_HORNER_DEGREE,
                    max_terms=MAX_HORNER_TERMS,
                    max_generated_nodes=MAX_HORNER_GENERATED_NODES,
                )
                if isinstance(horner, BoundedHornerRefusal):
                    detail = f"optimization Horner {horner.resource}"
                    if not horner.resource.endswith("refusal"):
                        detail += " refused"
                    if horner.observed is not None and horner.configured is not None:
                        detail += f" (measured {horner.observed}, configured {horner.configured})"
                    qualifications.append(detail)
                elif isinstance(horner, BoundedHornerCandidate):
                    # Rendering is bounded discovery evidence; parsing and structural
                    # replacement are transition materialization work.
                    rendered = horner.rendered
                    path = occurrence.path
                    append(
                        _CandidateDescriptor(
                            "horner",
                            ("horner", target, render(expression).sympy, path, rendered),
                            lambda target=target, expression=expression,
                            occurrence=occurrence, rendered=rendered: _horner_candidate(
                                target, expression, occurrence, rendered
                            ),
                        )
                    )
                if occurrence.scope.binders:
                    binding = occurrence.scope.binders[-1]
                    raw_symbols = _free_symbols(node)
                    useful = (
                        isinstance(node, (BinaryExpression, Call))
                        and expression_node_count(node) > 1
                    )
                    if (
                        useful
                        and binding.name not in raw_symbols
                        and occurrence.path[: len(binding.path) + 1] == (*binding.path, 2)
                    ):
                        outer_scope = _EvaluationScope(
                            occurrence.scope.output_indices,
                            occurrence.scope.output_bindings,
                            occurrence.scope.binders[:-1],
                        )
                        intermediate_scope = _smallest_scope(node, outer_scope)
                        append(
                            _generated_replacement_descriptor(
                                kind="iterator_invariant_hoisting",
                                target=target,
                                original=expression,
                                occurrences=(occurrence,),
                                generated_name=generated_name,
                                intermediate_expression=node,
                                intermediate_scope=intermediate_scope,
                            )
                        )
        try:
            sharing_descriptors = _cross_equation_descriptors(
                computed, occurrences_by_target, generated_name
            )
        except ExpressionTooComplex:
            qualifications.append(
                "optimization per-candidate transformation nodes budget exhausted "
                f"(measured >{MAX_OPTIMIZATION_TRANSFORM_NODES}, "
                f"configured {MAX_OPTIMIZATION_TRANSFORM_NODES})"
            )
        else:
            for descriptor in sharing_descriptors:
                append(descriptor)
    except _BudgetExhausted as error:
        qualifications.append(str(error))
    return collector.lanes_for(lane_prefix), tuple(dict.fromkeys(qualifications))


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
            kind, target, render(original).sympy, paths, generated_name,
            render(intermediate_expression).sympy, _scope_sort_key(intermediate_scope),
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
            kind, target, original, proposed, occurrences, transformed_targets,
            intermediate_expression, intermediate_scope,
        ),
        lambda: _CandidateComputation(
            kind, target, original, proposed, occurrences, transformed_targets,
            intermediate_name, intermediate_expression, intermediate_scope,
        ),
    )


def _round_robin_descriptors(
    lanes: Iterable[tuple[tuple[object, ...], tuple[_CandidateDescriptor, ...]]],
) -> tuple[tuple[tuple[object, ...], _CandidateDescriptor], ...]:
    """Select one stable descriptor from every live lane in each round."""
    active = [(key, values, 0) for key, values in sorted(lanes, key=lambda item: item[0]) if values]
    selected: list[tuple[tuple[object, ...], _CandidateDescriptor]] = []
    while active:
        next_round: list[tuple[tuple[object, ...], tuple[_CandidateDescriptor, ...], int]] = []
        for key, values, position in active:
            selected.append((key, values[position]))
            position += 1
            if position < len(values):
                next_round.append((key, values, position))
        active = next_round
    return tuple(selected)


def _generate_candidates(  # pyright: ignore[reportUnusedFunction]
    computed: RetainedComputation, budget: _OptimizationBudget
) -> tuple[tuple[_CandidateComputation, ...], tuple[str, ...]]:
    """Compatibility projection over the stable built-in family lanes."""
    collector = _RetainedLaneCollector(budget)
    _lanes, qualifications = _generate_candidate_lanes(computed, budget, collector)
    scheduled = collector.schedule()
    exhaustion = collector.exhaustion()
    if exhaustion is not None:
        qualifications = (*qualifications, exhaustion)
    return tuple(candidate for _key, candidate in scheduled), tuple(qualifications)


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


def _aggregate_scope(  # pyright: ignore[reportUnusedFunction]
    analysis: WorkAnalysis,
    scope: _EvaluationScope,
    context: WorkContext,
    *,
    output_domains: tuple[OutputDomain, ...] = (),
    reasoning: ReasoningContext | None = None,
) -> WorkAnalysis | None:
    sum_binders = tuple(
        item for item in scope.binders if item.lower is not None and item.upper is not None
    )
    scoped = WorkContext(
        definitions=context.definitions,
        primitives=context.primitives,
        variable_domains=context.variable_domains,
        integer_symbols=context.integer_symbols | frozenset(scope.output_indices),
        nonnegative_symbols=context.nonnegative_symbols,
        call_stack=context.call_stack,
        lexical_values=context.lexical_values,
    )
    for binding in scope.binders:
        if binding.value is not None:
            scoped = scoped.with_lexical_value(binding.name, binding.value)
        elif binding.lower is not None and binding.upper is not None:
            scoped = scoped.with_integer_symbol(binding.name)
    result = (
        substitute_analysis(analysis, scoped.lexical_values) if scoped.lexical_values else analysis
    )
    for binding in reversed(sum_binders):
        assert binding.lower is not None and binding.upper is not None
        result, unresolved = aggregate_analysis(
            result,
            binding.name,
            scoped.resolve_lexical(binding.lower),
            scoped.resolve_lexical(binding.upper),
            scoped,
            f"optimization intermediate binder {binding.name}",
        )
        if unresolved is not None:
            result.unresolved.add(unresolved)
    if scope.output_bindings and output_domains and reasoning is not None:
        selected = tuple(
            domain for domain in output_domains if domain.index in scope.output_indices
        )
        if len(selected) != len(scope.output_indices):
            return None
        result, _uses = aggregate_output_analysis(
            result,
            selected,
            scope.output_indices,
            scoped,
            reasoning,
            "optimization intermediate",
        )
        return result
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


def _candidate_target_work(  # pyright: ignore[reportUnusedFunction]
    target: str,
    proposed: Expression,
    computed: RetainedComputation,
    context: WorkContext,
    reasoning: ReasoningContext,
) -> WorkAnalysis:
    equation = next((item for item in computed.equations if item.name == target), None)
    indices = equation.domain_order if equation is not None else ()
    scoped = WorkContext(
        definitions=context.definitions,
        primitives=context.primitives,
        variable_domains=context.variable_domains,
        integer_symbols=context.integer_symbols | frozenset(indices),
        nonnegative_symbols=context.nonnegative_symbols,
        call_stack=context.call_stack,
        lexical_values=context.lexical_values,
    )
    result = analyze_work(proposed, scoped)
    if equation is not None:
        result, _uses = aggregate_output_analysis(
            result,
            equation.output_domains,
            equation.domain_order,
            scoped,
            reasoning,
            f"optimization equation {target}",
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


def _abstract_opaque_atoms(left: Expression, right: Expression) -> tuple[Expression, Expression]:
    """Give opaque aggregate/call atoms stable proof-local identities."""
    atoms: dict[object, Symbol] = {}
    reserved = _all_symbol_names(left) | _all_symbol_names(right)

    def atom(value: Expression) -> Symbol:
        try:
            key: object = (type(value).__name__, render(value).sympy)
        except NormalizationError:
            key = value
        existing = atoms.get(key)
        if existing is not None:
            return existing
        position = len(atoms)
        name = f"optimization_proof_atom_{position}"
        while name in reserved:
            position += 1
            name = f"optimization_proof_atom_{position}"
        reserved.add(name)
        result = Symbol(name)
        atoms[key] = result
        return result

    def visit(value: Expression) -> Expression:
        if isinstance(value, (Call, IndexedValue, Sum)):
            return atom(value)
        if isinstance(value, BinaryExpression):
            return BinaryExpression(value.operator, visit(value.left), visit(value.right))
        if isinstance(value, Let):
            return Let(value.name, visit(value.value), visit(value.body))
        return value

    return visit(left), visit(right)


def _exact_output_equivalence(
    left: Expression,
    right: Expression,
    reasoning: ReasoningContext | None,
) -> QueryAnswer:
    """Use the same bounded exact normalization for transition and final proofs."""
    reserved = _all_symbol_names(left) | _all_symbol_names(right)
    left_canonical = _canonical_output_expression(left, (), reserved)
    right_canonical = _canonical_output_expression(right, (), reserved)
    try:
        normalized_equal = (
            left_canonical == right_canonical
            or render(left_canonical).sympy == render(right_canonical).sympy
        )
    except NormalizationError:
        normalized_equal = False
    if normalized_equal:
        return QueryAnswer(
            conclusion="proved",
            evidence=IdentityEvidence(
                statement="checked complete candidate reconstructs every retained output"
            ),
        )
    answer = equivalence_answer(left, right, reasoning)
    if answer.conclusion in {"proved", "proved_under_assumptions"}:
        return answer
    abstracted_left, abstracted_right = _abstract_opaque_atoms(left_canonical, right_canonical)
    abstracted = equivalence_answer(abstracted_left, abstracted_right, reasoning)
    return abstracted if not abstracted.conditions else answer


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
    transformations = candidate.transformed_targets or (
        (candidate.target, candidate.original, candidate.proposed),
    )
    transformation_nodes = sum(
        expression_node_count(proposed) for _target, _original, proposed in transformations
    )
    try:
        budget.transformation(transformation_nodes)
    except _BudgetExhausted as error:
        return _Exhausted(str(error))
    # Candidate generation is untrusted. Reparse its complete computation through
    # the ordinary retained-analysis seam before any proof or work projection.
    from py_science.formula.service import (
        _analyze_computation,  # pyright: ignore[reportPrivateUsage]
    )

    try:
        complete = _complete_candidate(candidate, request, computed)
    except ValidationError:
        return _Rejected("complete candidate exceeds ordinary request bounds")
    replayed = _analyze_computation(complete)
    if isinstance(replayed, AnalysisFailure):
        return _Rejected("complete candidate does not pass ordinary analysis")
    expansion_budget = ExpansionBudget(remaining=MAX_OPTIMIZATION_TRANSFORM_NODES)
    reserved: set[str] = set()
    for _target, expression, _indices, _domains in _target_inputs(computed):
        reserved.update(_all_symbol_names(expression))
    answers: list[QueryAnswer] = []

    def abstract_opaque_atoms(left: Expression, right: Expression) -> tuple[Expression, Expression]:
        atoms: dict[object, Symbol] = {}
        reserved_atoms = _all_symbol_names(left) | _all_symbol_names(right)

        def atom(value: Expression) -> Symbol:
            try:
                key: object = (type(value).__name__, render(value).sympy)
            except NormalizationError:
                key = value
            existing = atoms.get(key)
            if existing is not None:
                return existing
            position = len(atoms)
            name = f"optimization_proof_atom_{position}"
            while name in reserved_atoms:
                position += 1
                name = f"optimization_proof_atom_{position}"
            reserved_atoms.add(name)
            result = Symbol(name)
            atoms[key] = result
            return result

        def visit(value: Expression) -> Expression:
            if isinstance(value, (Call, IndexedValue, Sum)):
                return atom(value)
            if isinstance(value, BinaryExpression):
                return BinaryExpression(value.operator, visit(value.left), visit(value.right))
            if isinstance(value, Sum):
                return Sum(visit(value.body), value.index, visit(value.lower), visit(value.upper))
            if isinstance(value, Let):
                return Let(value.name, visit(value.value), visit(value.body))
            return value

        return visit(left), visit(right)

    def retained_output(analyzed: RetainedComputation, target: str) -> Expression:
        if target == "expression":
            assert analyzed.expression is not None
            return analyzed.expression
        return next(item.formula.right for item in analyzed.equations if item.name == target)

    try:
        # Proof expansion is deliberately downstream of complete-candidate
        # validation and reads the replayed outputs themselves. It never supplies
        # candidate work or placement semantics.
        for target, _original, _proposed in transformations:
            original_expanded = MappedOutputExpander(
                computed, expansion_budget, set(reserved)
            ).expand(retained_output(computed, target))
            expanded = MappedOutputExpander(replayed, expansion_budget, set(reserved)).expand(
                retained_output(replayed, target)
            )
            try:
                budget.proof(
                    expression_node_count(original_expanded) + expression_node_count(expanded)
                )
            except _BudgetExhausted as error:
                return _Exhausted(str(error))
            answer = equivalence_answer(original_expanded, expanded, reasoning)
            normalized_equal = False
            if answer.conclusion not in {"proved", "proved_under_assumptions"}:
                canonical_reserved = _all_symbol_names(original_expanded) | _all_symbol_names(
                    expanded
                )
                original_canonical = _canonical_output_expression(
                    original_expanded, (), canonical_reserved
                )
                expanded_canonical = _canonical_output_expression(expanded, (), canonical_reserved)
                try:
                    normalized_equal = (
                        original_canonical == expanded_canonical
                        or render(original_canonical).sympy == render(expanded_canonical).sympy
                    )
                except NormalizationError:
                    normalized_equal = False
                if not normalized_equal:
                    abstracted_original, abstracted_expanded = abstract_opaque_atoms(
                        original_canonical, expanded_canonical
                    )
                    abstracted_answer = equivalence_answer(
                        abstracted_original, abstracted_expanded, reasoning
                    )
                    if not abstracted_answer.conditions:
                        answer = abstracted_answer
            if normalized_equal:
                answer = QueryAnswer(
                    conclusion="proved",
                    evidence=IdentityEvidence(
                        statement="checked complete candidate reconstructs every retained output"
                    ),
                )
            if answer.conclusion not in {"proved", "proved_under_assumptions"}:
                return _Rejected("candidate output equivalence is not proved")
            if not isinstance(answer.evidence, IdentityEvidence):
                return _Rejected("candidate proof has no exact identity evidence")
            answers.append(answer)
    except ExpressionTooComplex:
        return _Exhausted(
            "optimization substitution nodes budget exhausted "
            f"(measured >{MAX_OPTIMIZATION_TRANSFORM_NODES}, "
            f"configured {MAX_OPTIMIZATION_TRANSFORM_NODES})"
        )

    assert reasoning is not None
    after = _as_work(replayed.aggregate_analysis)
    before = _as_work(computed.aggregate_analysis)
    if after.unknown_costs or after.unresolved or after.direct_work_blockers:
        return _Rejected("candidate aggregate work is unavailable")
    if before.unknown_costs or before.unresolved or before.direct_work_blockers:
        return _Rejected("retained aggregate work is unavailable")
    try:
        budget.work(
            expression_node_count(before.total_work) + expression_node_count(after.total_work)
        )
    except _BudgetExhausted as error:
        return _Exhausted(str(error))
    objective_before = project_optimization_objective(before, request.optimization.objective)
    objective_after = project_optimization_objective(after, request.optimization.objective)
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(
            work=objective_after,
            unknown_costs=frozenset(after.unknown_costs),
            direct_work_blockers=frozenset(after.direct_work_blockers),
        ),
        AggregateWorkComparisonInput(
            work=objective_before,
            unknown_costs=frozenset(before.unknown_costs),
            direct_work_blockers=frozenset(before.direct_work_blockers),
        ),
        reasoning,
        semantic_established=True,
    )
    if relation.status != "first_lower" or relation.delta is None:
        return _Rejected("candidate has no proved positive aggregate-work reduction")
    if exact_work_sign(objective_before) in {-1, 0} or exact_work_sign(objective_after) == -1:
        return _Rejected("candidate work before must be positive and work after nonnegative")

    work_budget = WorkRenderBudget()
    try:
        objective_before_rendered = render_work(objective_before, work_budget)
        objective_after_rendered = render_work(objective_after, work_budget)
        objective_savings = render_work(relation.delta, work_budget)
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
        return _Exhausted(
            "optimization rendering budget exhausted "
            f"(measured >{MAX_OPTIMIZATION_TRANSFORM_NODES}, "
            f"configured {MAX_OPTIMIZATION_TRANSFORM_NODES})"
        )

    conditions = tuple(dict.fromkeys(item for answer in answers for item in answer.conditions))
    assumptions = _unique_uses(item for answer in answers for item in answer.assumptions_used)
    conditions = tuple(dict.fromkeys((*conditions, *relation.conditions)))
    assumptions = _unique_uses((*assumptions, *relation.assumptions_used))
    conclusion: Literal["proved", "proved_under_assumptions"] = (
        "proved_under_assumptions" if conditions or assumptions else "proved"
    )
    raw_transformations = candidate.transformed_targets or (
        (candidate.target, candidate.original, candidate.proposed),
    )
    # Trace transformations retain their public target-local proposed state.
    # The separate complete candidate carries the post-step computation.
    transformations = tuple(
        OptimizationTransformation(
            target=(
                OptimizationTarget(kind="expression")
                if target_name == "expression" and computed.expression is not None
                else OptimizationTarget(kind="equation", name=target_name)
            ),
            occurrences=tuple(
                OptimizationOccurrence(
                    path=item.path,
                    binders=item.binders,
                    output_indices=item.scope.output_indices,
                )
                for item in candidate.occurrences
                if item.target == target_name
            ),
            original=_interpretation(original_expression),
            proposed=_interpretation(proposed_expression),
        )
        for target_name, original_expression, proposed_expression in raw_transformations
    )
    evidence = IdentityEvidence(
        statement="checked exact symbolic equivalence for every transformed retained output"
    )
    suggestion = OptimizationSuggestion(
        kind=candidate.kind,
        transformations=transformations,
        intermediate=intermediate,
        conclusion=conclusion,
        evidence=evidence,
        conditions=conditions,
        assumptions_used=assumptions,
        objective_before=objective_before_rendered,
        objective_after=objective_after_rendered,
        objective_savings=objective_savings,
        ordering=OptimizationOrdering(position=1, relation_to_previous=None),
    )
    return _Accepted(suggestion, complete, relation.delta, replayed)


def _qualifications_compatible(
    conditions: tuple[str, ...], request: AnalysisRequest
) -> bool:
    """Refuse a final whose accumulated exact-proof requirements conflict.

    Equivalence intentionally publishes unresolved denominator obligations.  A
    direct final proof therefore cannot blindly union those obligations with
    trace requirements or submitted assumptions: ``x != 0`` and ``x == 0``
    would describe no common qualified result.  This is deliberately a small
    structural check at the proof seam, not a new public assumption policy.
    """
    relationships: list[Relationship] = []
    for assumption in request.assumptions:
        parsed = parse_expression(assumption.relationship)
        if isinstance(parsed, Relationship):
            relationships.append(parsed)
    equalities: set[tuple[str, str]] = set()
    inequalities: set[tuple[str, str]] = set()
    # Denominator obligations use the deliberately minimal ``x != 0`` wire
    # spelling, which the mathematical request parser quite properly does not
    # accept as an input relationship.  Compare that bounded proof spelling
    # structurally here; opaque future proof conditions remain conservative
    # qualifications rather than becoming a new parser surface.
    for condition in conditions:
        separator = " != " if " != " in condition else " == " if " == " in condition else None
        if separator is None:
            continue
        left, right = condition.split(separator, 1)
        pair = (left, right) if left <= right else (right, left)
        (inequalities if separator == " != " else equalities).add(pair)
    for relationship in relationships:
        try:
            left, right = render(relationship.left).sympy, render(relationship.right).sympy
        except NormalizationError:
            return False
        pair = (left, right) if left <= right else (right, left)
        if relationship.operator is RelationshipOperator.EQUAL:
            equalities.add(pair)
    return not bool(equalities & inequalities)


def _original_final_suggestion(
    local: OptimizationSuggestion,
    trace: tuple[tuple[OptimizationSuggestion, AnalysisRequest], ...],
    root: RetainedComputation,
    final: RetainedComputation,
    request: AnalysisRequest,
    reasoning: ReasoningContext,
    budget: _OptimizationBudget,
) -> tuple[OptimizationSuggestion, Expression] | _Rejected | _Exhausted:
    """Independently prove and measure a retained final against the submitted root."""
    try:
        budget.retain()
    except _BudgetExhausted as error:
        return _Exhausted(str(error))
    root_work = _as_work(root.aggregate_analysis)
    final_work = _as_work(final.aggregate_analysis)
    if (
        root_work.unknown_costs
        or root_work.unresolved
        or root_work.direct_work_blockers
        or final_work.unknown_costs
        or final_work.unresolved
        or final_work.direct_work_blockers
    ):
        return _Rejected("final aggregate work is unavailable")
    root_objective = project_optimization_objective(root_work, request.optimization.objective)
    final_objective = project_optimization_objective(final_work, request.optimization.objective)
    try:
        budget.work(expression_node_count(root_objective) + expression_node_count(final_objective))
    except _BudgetExhausted as error:
        return _Exhausted(str(error))
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(work=final_objective),
        AggregateWorkComparisonInput(work=root_objective),
        reasoning,
        semantic_established=True,
    )
    if relation.status != "first_lower" or relation.delta is None:
        return _Rejected("final has no proved positive original-relative reduction")
    if exact_work_sign(root_objective) in {-1, 0} or exact_work_sign(final_objective) == -1:
        return _Rejected("final work before must be positive and work after nonnegative")
    reserved: set[str] = set()
    for _target, expression, _indices, _domains in _target_inputs(root):
        reserved.update(_all_symbol_names(expression))
    try:
        root_outputs = (
            [("expression", root.expression)]
            if root.expression is not None
            else [(item.name, item.formula.right) for item in root.equations]
        )
        final_outputs = (
            {"expression": final.expression}
            if final.expression is not None
            else {item.name: item.formula.right for item in final.equations}
        )
        answers: list[QueryAnswer] = []
        for target, original in root_outputs:
            assert original is not None and final_outputs.get(target) is not None
            left = MappedOutputExpander(
                root, ExpansionBudget(remaining=MAX_OPTIMIZATION_TRANSFORM_NODES), set(reserved)
            ).expand(original)
            right = MappedOutputExpander(
                final, ExpansionBudget(remaining=MAX_OPTIMIZATION_TRANSFORM_NODES), set(reserved)
            ).expand(final_outputs[target])
            budget.proof(expression_node_count(left) + expression_node_count(right))
            answer = _exact_output_equivalence(left, right, reasoning)
            if answer.conclusion not in {"proved", "proved_under_assumptions"} or not isinstance(
                answer.evidence, IdentityEvidence
            ):
                return _Rejected("final output equivalence is not proved")
            answers.append(answer)
        render_budget = WorkRenderBudget()
        conditions = tuple(
            dict.fromkeys(
                (
                    *[condition for step, _candidate in trace for condition in step.conditions],
                    *[item for answer in answers for item in answer.conditions],
                    *relation.conditions,
                )
            )
        )
        assumptions = _unique_uses(
            (
                *[use for step, _candidate in trace for use in step.assumptions_used],
                *[item for answer in answers for item in answer.assumptions_used],
                *relation.assumptions_used,
            )
        )
        if not _qualifications_compatible(conditions, request):
            return _Rejected("final proof qualifications conflict with submitted assumptions")
        return (
            local.model_copy(
                update={
                    "conclusion": (
                        "proved_under_assumptions" if conditions or assumptions else "proved"
                    ),
                    "evidence": IdentityEvidence(
                        statement=(
                            "checked exact symbolic equivalence from submitted computation "
                            "to final candidate"
                        )
                    ),
                    "conditions": conditions,
                    "assumptions_used": assumptions,
                    "objective_before": render_work(root_objective, render_budget),
                    "objective_after": render_work(final_objective, render_budget),
                    "objective_savings": render_work(relation.delta, render_budget),
                }
            ),
            relation.delta,
        )
    except _BudgetExhausted as error:
        return _Exhausted(str(error))
    except (ExpressionTooComplex, NormalizationError):
        # These backend refusals are candidate-local verification failures, not
        # evidence that one of the explicit search counters was exhausted.
        return _Rejected("final candidate exact proof could not be normalized")


def _suggestion_order(left: OptimizationSuggestion, right: OptimizationSuggestion) -> int:
    if (left.conclusion == "proved") != (right.conclusion == "proved"):
        return -1 if left.conclusion == "proved" else 1
    try:
        left_savings = Fraction(left.objective_savings)
        right_savings = Fraction(right.objective_savings)
    except (ValueError, ZeroDivisionError):
        left_savings = right_savings = None
    if left_savings is not None and right_savings is not None and left_savings != right_savings:
        return -1 if left_savings > right_savings else 1
    left_key = (
        tuple(
            (item.target.name or "", item.occurrences[0].path, item.proposed.normalized_sympy)
            for item in left.transformations
        ),
        left.kind,
    )
    right_key = (
        tuple(
            (item.target.name or "", item.occurrences[0].path, item.proposed.normalized_sympy)
            for item in right.transformations
        ),
        right.kind,
    )
    return (left_key > right_key) - (left_key < right_key)


def _accepted_order(
    left: _Accepted,
    right: _Accepted,
    reasoning: ReasoningContext,
    budget: _OptimizationBudget,
) -> int:
    base = _suggestion_order(left.suggestion, right.suggestion)
    if (left.suggestion.conclusion == "proved") != (right.suggestion.conclusion == "proved"):
        return base
    try:
        left_exact = Fraction(left.suggestion.objective_savings)
        right_exact = Fraction(right.suggestion.objective_savings)
    except (ValueError, ZeroDivisionError):
        left_exact = right_exact = None
    if left_exact is not None and right_exact is not None:
        return base
    if (
        left.suggestion.conditions != right.suggestion.conditions
        or left.suggestion.assumptions_used != right.suggestion.assumptions_used
    ):
        return base
    budget.work(
        expression_node_count(left.savings_expression)
        + expression_node_count(right.savings_expression)
    )
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(work=left.savings_expression),
        AggregateWorkComparisonInput(work=right.savings_expression),
        reasoning,
        semantic_established=True,
    )
    if relation.conditions or relation.assumptions_used:
        return base
    if relation.status == "first_lower":
        return 1
    if relation.status == "second_lower":
        return -1
    return base


def _adjacent_ordering_relation(
    previous: _Accepted,
    current: _Accepted,
    reasoning: ReasoningContext,
    budget: _OptimizationBudget,
) -> Literal["previous_proved_superior", "deterministic_non_superiority"]:
    if (
        previous.suggestion.conclusion != current.suggestion.conclusion
        or previous.suggestion.conditions != current.suggestion.conditions
        or previous.suggestion.assumptions_used != current.suggestion.assumptions_used
    ):
        return "deterministic_non_superiority"
    try:
        previous_exact = Fraction(previous.suggestion.objective_savings)
        current_exact = Fraction(current.suggestion.objective_savings)
    except (ValueError, ZeroDivisionError):
        previous_exact = current_exact = None
    if previous_exact is not None and current_exact is not None:
        return (
            "previous_proved_superior"
            if previous_exact > current_exact
            else "deterministic_non_superiority"
        )
    budget.work(
        expression_node_count(previous.savings_expression)
        + expression_node_count(current.savings_expression)
    )
    relation = compare_aggregate_work(
        AggregateWorkComparisonInput(work=previous.savings_expression),
        AggregateWorkComparisonInput(work=current.savings_expression),
        reasoning,
        semantic_established=True,
    )
    if relation.conditions or relation.assumptions_used:
        return "deterministic_non_superiority"
    return (
        "previous_proved_superior"
        if relation.status == "second_lower"
        else "deterministic_non_superiority"
    )


def _candidate_semantic_key(  # pyright: ignore[reportUnusedFunction]
    candidate: _CandidateComputation,
) -> tuple[object, ...]:
    """Legacy local-proposal identity retained for focused generator tests only."""
    transformations = candidate.transformed_targets or (
        (candidate.target, candidate.original, candidate.proposed),
    )
    return (
        tuple((target, proposed) for target, _original, proposed in transformations),
        candidate.intermediate_expression,
        candidate.intermediate_scope,
    )


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_state_key(
    request: AnalysisRequest,
    computed: RetainedComputation,
    generated_names: tuple[str, ...],
) -> tuple[object, ...]:
    """Serialize complete computation semantics independently of search history."""
    names = tuple(dict.fromkeys(generated_names))
    context = (
        request.syntax.value,
        _stable_json(
            {name: value.model_dump(mode="json") for name, value in request.variables.items()}
        ),
        _stable_json([value.model_dump(mode="json") for value in request.functions]),
        _stable_json([value.model_dump(mode="json") for value in request.primitive_costs]),
        _stable_json([value.model_dump(mode="json") for value in request.assumptions]),
        _stable_json([value.model_dump(mode="json") for value in request.definitions]),
        tuple(request.outputs),
    )
    def serialize(generated: dict[str, str]) -> tuple[object, ...]:
        if computed.expression is not None:
            canonical = _canonical_output_expression(computed.expression, (), free_names=generated)
            return (*context, "expression", render(canonical).sympy)

        equations: list[tuple[object, ...]] = []
        for equation in sorted(
            computed.equations, key=lambda item: generated.get(item.name, item.name)
        ):
            reserved = _all_symbol_names(equation.formula.right)
            for domain in equation.output_domains:
                reserved.update(_all_symbol_names(domain.lower))
                reserved.update(_all_symbol_names(domain.upper))
            canonical_indices = _canonical_output_index_names(len(equation.domain_order), reserved)
            index_names = dict(zip(equation.domain_order, canonical_indices, strict=True))
            canonical_right = _canonical_output_expression(
                equation.formula.right,
                equation.domain_order,
                reserved,
                canonical_indices,
                generated,
            )
            domains = tuple(
                (
                    index_names[domain.index],
                    render(
                        _canonical_output_expression(
                            domain.lower,
                            equation.domain_order,
                            reserved,
                            canonical_indices,
                            generated,
                        )
                    ).sympy,
                    render(
                        _canonical_output_expression(
                            domain.upper,
                            equation.domain_order,
                            reserved,
                            canonical_indices,
                            generated,
                        )
                    ).sympy,
                )
                for domain in equation.output_domains
            )
            constraints = tuple(
                sorted(
                    (
                        name,
                        index_names[target],
                        relationship.operator.value,
                        render(
                            _canonical_output_expression(
                                relationship.left,
                                equation.domain_order,
                                reserved,
                                canonical_indices,
                                generated,
                            )
                        ).sympy,
                        render(
                            _canonical_output_expression(
                                relationship.right,
                                equation.domain_order,
                                reserved,
                                canonical_indices,
                                generated,
                            )
                        ).sympy,
                    )
                    for name, target, relationship in equation.constraints
                )
            )
            equations.append(
                (
                    generated.get(equation.name, equation.name),
                    tuple(canonical_indices),
                    render(canonical_right).sympy,
                    domains,
                    constraints,
                )
            )
        return (*context, "system", tuple(equations))
    # Generated producers are binders in the complete state, not trace-order
    # labels.  Depth two has at most two, so selecting the least complete
    # serialization across their bijections is bounded and capture-avoiding.
    return min(
        serialize(
            {name: f"optimization_generated_{position}" for position, name in enumerate(order)}
        )
        for order in permutations(names)
    ) if names else serialize({})


def _trace_key(
    trace: tuple[tuple[OptimizationSuggestion, AnalysisRequest], ...],
) -> tuple[object, ...]:
    return tuple(
        (
            suggestion.kind,
            tuple(
                (
                    item.target.kind,
                    item.target.name or "",
                    tuple(occurrence.path for occurrence in item.occurrences),
                    item.proposed.normalized_sympy,
                )
                for item in suggestion.transformations
            ),
            candidate.model_dump_json(exclude_none=True),
        )
        for suggestion, candidate in trace
    )


def _state_preference(state: _SearchState) -> tuple[object, ...]:
    return state.depth, _trace_key(state.trace), state.concrete_identity


def _complete_candidate_schedule(  # pyright: ignore[reportUnusedFunction]
    candidates: tuple[_CandidateComputation, ...],
) -> tuple[_CandidateComputation, ...]:
    """Bound reanalysis without starving a shipped family or the candidate tail."""
    if len(candidates) <= MAX_OPTIMIZATION_COMPLETE_REANALYSES:
        return candidates

    selected: set[int] = set()
    for position, candidate in enumerate(candidates):
        if any(candidates[index].kind == candidate.kind for index in selected):
            continue
        selected.add(position)
        if len(selected) == MAX_OPTIMIZATION_COMPLETE_REANALYSES:
            tail = len(candidates) - 1
            tail_kind = candidates[tail].kind
            selected.remove(
                next(index for index in selected if candidates[index].kind == tail_kind)
            )
            selected.add(tail)
            return tuple(candidates[index] for index in sorted(selected))

    remaining = tuple(index for index in range(len(candidates)) if index not in selected)
    slots = MAX_OPTIMIZATION_COMPLETE_REANALYSES - len(selected)
    if slots == 1:
        selected.add(remaining[-1])
    else:
        last = len(remaining) - 1
        for sample in range(slots):
            selected.add(remaining[(sample * last) // (slots - 1)])
    return tuple(candidates[index] for index in sorted(selected))


def _unique_qualifications(values: Iterable[str]) -> tuple[str, ...]:
    """Keep the deterministic first measurement for each bounded resource."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.split(" (measured", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
        if len(result) == 128:
            break
    return tuple(result)


def _optimization_report(  # pyright: ignore[reportUnusedFunction]
    request: AnalysisRequest,
    computed: RetainedComputation,
    context: WorkContext,
    budget_config: _OptimizationBudgetConfig | None = None,
) -> OptimizationReport:
    """Generate bounded candidates and publish only common-verifier acceptances."""
    limit = request.optimization.max_suggestions
    if limit == 0:
        return OptimizationReport(requested_limit=0, status="disabled")
    configuration = budget_config or _default_budget_config()
    whole = _WholeTransitionBudget(configuration)
    depth_one_config = replace(
        configuration, inspections=configuration.inspections, expanded_parents=1
    )
    depth_two_config = replace(
        configuration,
        inspections=configuration.depth_two_inspections,
        expanded_parents=configuration.expanded_parents,
    )
    final_config = replace(
        configuration,
        retained_states=configuration.final_states,
        proofs=configuration.final_proofs,
        proof_nodes=configuration.final_proof_nodes,
        work_nodes=configuration.final_work_nodes,
    )
    depth_one_budget = _OptimizationBudget(depth_one_config, "depth-one", whole)
    depth_two_budget = _OptimizationBudget(depth_two_config, "depth-two", whole)
    final_budget = _OptimizationBudget(final_config, "final-acceptance")
    ranking_budget = _OptimizationBudget(configuration, "ranking")
    qualifications: list[str] = []
    reasoning = _reasoning(request, computed)
    if reasoning is None:
        return OptimizationReport(
            requested_limit=limit,
            status="incomplete",
            qualifications=(
                "optimization proof context nodes budget exhausted "
                f"(measured >{MAX_OPTIMIZATION_PROOF_NODES}, "
                f"configured {MAX_OPTIMIZATION_PROOF_NODES})",
            ),
        )

    def generated_names(
        parent: _SearchState | None, candidate: _CandidateComputation
    ) -> tuple[str, ...]:
        names = parent.generated_names if parent is not None else ()
        if candidate.intermediate_name is None or candidate.intermediate_name in names:
            return names
        return (*names, candidate.intermediate_name)

    def state_from(
        outcome: _Accepted,
        parent: _SearchState | None,
        candidate: _CandidateComputation,
        depth: int,
    ) -> _SearchState:
        assert outcome.computed is not None
        names = generated_names(parent, candidate)
        trace = (
            *(parent.trace if parent is not None else ()),
            (outcome.suggestion, outcome.candidate),
        )
        after = _as_work(outcome.computed.aggregate_analysis)
        return _SearchState(
            request=outcome.candidate,
            computed=outcome.computed,
            objective_total=project_optimization_objective(after, request.optimization.objective),
            canonical_key=_canonical_state_key(outcome.candidate, outcome.computed, names),
            depth=depth,
            generated_names=names,
            trace=trace,
            concrete_identity=outcome.candidate.model_dump_json(exclude_none=True),
            local_savings=outcome.savings_expression,
        )

    def admit(
        population: dict[tuple[object, ...], _SearchState],
        state: _SearchState,
        budget: _OptimizationBudget,
    ) -> None:
        existing = population.get(state.canonical_key)
        if existing is not None:
            if _state_preference(state) < _state_preference(existing):
                population[state.canonical_key] = state
            return
        try:
            budget.retain()
        except _BudgetExhausted as error:
            qualifications.append(str(error))
            return
        population[state.canonical_key] = state

    # Depth one expands exactly the unreturned root through the eight fixed lanes.
    depth_one: dict[tuple[object, ...], _SearchState] = {}
    try:
        depth_one_budget.parent()
        root_collector = _RetainedLaneCollector(depth_one_budget)
        _root_lanes, generation_qualifications = _generate_candidate_lanes(
            computed, depth_one_budget, root_collector
        )
        qualifications.extend(generation_qualifications)
        root_schedule = root_collector.schedule()
        exhaustion = root_collector.exhaustion()
        if exhaustion is not None:
            qualifications.append(exhaustion)
        for _lane, candidate in root_schedule:
            try:
                depth_one_budget.reanalysis()
            except _BudgetExhausted as error:
                qualifications.append(str(error))
                break
            outcome = _verify_candidate(
                candidate, request, computed, context, reasoning, depth_one_budget
            )
            if isinstance(outcome, _Exhausted):
                qualifications.append(outcome.reason)
            elif not isinstance(outcome, _Rejected):
                admit(depth_one, state_from(outcome, None, candidate, 1), depth_one_budget)
    except _BudgetExhausted as error:
        qualifications.append(str(error))

    # Depth two schedules canonical parent-family lanes globally, one proposal per
    # live lane per round, rather than letting any parent or family consume the depth.
    depth_two: dict[tuple[object, ...], _SearchState] = {}
    parent_by_lane: dict[tuple[object, ...], _SearchState] = {}
    depth_two_collector = _RetainedLaneCollector(depth_two_budget)
    for parent in sorted(depth_one.values(), key=lambda item: item.canonical_key):
        try:
            depth_two_budget.parent()
            _lanes, generation_qualifications = _generate_candidate_lanes(
                parent.computed, depth_two_budget, depth_two_collector, (parent.canonical_key,)
            )
            qualifications.extend(generation_qualifications)
        except _BudgetExhausted as error:
            qualifications.append(str(error))
            break
        for kind in _FAMILY_ORDER:
            parent_by_lane[(parent.canonical_key, kind)] = parent
    depth_two_schedule = depth_two_collector.schedule()
    exhaustion = depth_two_collector.exhaustion()
    if exhaustion is not None:
        qualifications.append(exhaustion)
    for lane_key, candidate in depth_two_schedule:
        try:
            depth_two_budget.reanalysis()
        except _BudgetExhausted as error:
            qualifications.append(str(error))
            break
        parent = parent_by_lane[lane_key]
        outcome = _verify_candidate(
            candidate,
            parent.request,
            parent.computed,
            context,
            reasoning,
            depth_two_budget,
        )
        if isinstance(outcome, _Exhausted):
            qualifications.append(outcome.reason)
        elif not isinstance(outcome, _Rejected):
            admit(depth_two, state_from(outcome, parent, candidate, 2), depth_two_budget)

    # Equal finals collapse across both depths before direct root-relative acceptance;
    # the lower depth, canonical trace, and concrete candidate choose the representative.
    final_states = dict(depth_one)
    for key, state in depth_two.items():
        existing = final_states.get(key)
        if existing is None or _state_preference(state) < _state_preference(existing):
            final_states[key] = state

    accepted: list[_Accepted] = []
    for state in sorted(final_states.values(), key=lambda item: item.canonical_key):
        final = _original_final_suggestion(
            state.trace[-1][0],
            state.trace,
            computed,
            state.computed,
            request,
            reasoning,
            final_budget,
        )
        if isinstance(final, _Exhausted):
            qualifications.append(final.reason)
            continue
        if isinstance(final, _Rejected):
            continue
        final_suggestion, final_savings = final
        accepted.append(
            _Accepted(
                final_suggestion,
                state.request,
                final_savings,
                state.computed,
                state.trace,
            )
        )

    try:
        accepted.sort(
            key=cmp_to_key(
                lambda left, right: _accepted_order(left, right, reasoning, ranking_budget)
            )
        )
    except _BudgetExhausted as error:
        qualifications.append(str(error))
        accepted.sort(
            key=cmp_to_key(lambda left, right: _suggestion_order(left.suggestion, right.suggestion))
        )
    selected = accepted[:limit]

    def plan(item: _Accepted) -> OptimizationPlan:
        candidate_request = item.candidate
        candidate = OptimizationCandidate(
            syntax=candidate_request.syntax,
            expression=candidate_request.expression,
            equations=candidate_request.equations,
            variables=candidate_request.variables,
            functions=candidate_request.functions,
            primitive_costs=candidate_request.primitive_costs,
            assumptions=candidate_request.assumptions,
            definitions=candidate_request.definitions,
            outputs=("expression",)
            if candidate_request.expression is not None
            else tuple(equation.name for equation in computed.equations),
        )
        # This canonical JSON identity is stable across the direct and passive surfaces.
        identity = candidate.model_dump_json(exclude_none=True)
        trace_items = item.trace or ((item.suggestion, item.candidate),)
        trace: list[OptimizationTraceStep] = []
        for step_suggestion, step_request in trace_items:
            step_candidate = OptimizationCandidate(
                syntax=step_request.syntax,
                expression=step_request.expression,
                equations=step_request.equations,
                variables=step_request.variables,
                functions=step_request.functions,
                primitive_costs=step_request.primitive_costs,
                assumptions=step_request.assumptions,
                definitions=step_request.definitions,
                outputs=("expression",)
                if step_request.expression is not None
                else tuple(equation.name for equation in computed.equations),
            )
            step_identity = step_candidate.model_dump_json(exclude_none=True)
            trace.append(
                OptimizationTraceStep(
                    kind=step_suggestion.kind,
                    transformations=step_suggestion.transformations,
                    intermediate=step_suggestion.intermediate,
                    conclusion=step_suggestion.conclusion,
                    evidence=step_suggestion.evidence,
                    conditions=step_suggestion.conditions,
                    assumptions_used=step_suggestion.assumptions_used,
                    objective_before=step_suggestion.objective_before,
                    objective_after=step_suggestion.objective_after,
                    objective_savings=step_suggestion.objective_savings,
                    candidate=step_candidate,
                    identity=step_identity,
                )
            )
        return OptimizationPlan(
            identity=identity,
            objective=request.optimization.objective,
            candidate=candidate,
            suggestion=item.suggestion,
            trace=tuple(trace),
        )

    ordered: list[_Accepted] = []
    for position, item in enumerate(selected, start=1):
        relation_to_previous = None
        if position > 1:
            try:
                relation_to_previous = _adjacent_ordering_relation(
                    ordered[-1], item, reasoning, ranking_budget
                )
            except _BudgetExhausted:
                relation_to_previous = "deterministic_non_superiority"
        ordered.append(
            _Accepted(
                item.suggestion.model_copy(
                    update={
                        "ordering": OptimizationOrdering(
                            position=position, relation_to_previous=relation_to_previous
                        )
                    }
                ),
                item.candidate,
                item.savings_expression,
                item.computed,
                item.trace,
            )
        )
    plans = tuple(plan(item) for item in ordered)
    return OptimizationReport(
        requested_limit=limit,
        status="incomplete" if qualifications else "complete",
        suggestions=tuple(item.suggestion for item in ordered),
        plans=plans,
        qualifications=_unique_qualifications(qualifications),
    )
