# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Candidate proof, acceptance, and direct-final verification."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from py_science.formula._analysis.occurrences import _EvaluationScope
from py_science.formula._analysis.retained import RetainedComputation, RetainedWorkAnalysis
from py_science.formula.domains import OutputDomain
from py_science.formula.equivalence import equivalence_answer
from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    Let,
    Relationship,
    RelationshipOperator,
    Sum,
    Symbol,
    expression_node_count,
)
from py_science.formula.mapped_outputs import ExpansionBudget, MappedOutputExpander
from py_science.formula.models import (
    OPTIMIZATION_FAMILY_TIERS,
    AnalysisFailure,
    AnalysisRequest,
    IdentityEvidence,
    Interpretation,
    OptimizationIntermediate,
    OptimizationOccurrence,
    OptimizationOrdering,
    OptimizationSuggestion,
    OptimizationTarget,
    OptimizationTransformation,
    QueryAnswer,
    RelationshipUse,
)
from py_science.formula.parser import parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.series import CheckedNestedSumResult, derive_checked_nested_sum
from py_science.formula.sympy_backend import NormalizationError, render
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

from .budgets import MAX_OPTIMIZATION_TRANSFORM_NODES, _BudgetExhausted, _OptimizationBudget
from .candidates import (
    _all_symbol_names,
    _CandidateComputation,
    _canonical_output_expression,
    _replace_paths,
    _target_inputs,
)
from .replay import _replay_candidate, _replay_request, _RetainedAnalyzer


@dataclass(frozen=True, slots=True)
class _Accepted:
    suggestion: OptimizationSuggestion
    candidate: AnalysisRequest
    savings_expression: Expression
    computed: RetainedComputation | None = None
    trace: tuple[tuple[OptimizationSuggestion, AnalysisRequest], ...] = ()


@dataclass(frozen=True, slots=True)
class _Rejected:
    reason: str


@dataclass(frozen=True, slots=True)
class _Exhausted:
    reason: str


type _CandidateOutcome = _Accepted | _Rejected | _Exhausted


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


def _intermediate_interpretation(expression: Expression) -> Interpretation:
    """Return the exact renderer spelling of an intermediate inside a Let state."""
    marker = "_optimization_binding"
    lexical = render(Let(marker, expression, Symbol(marker))).sympy
    prefix = f"Let({marker}, "
    return Interpretation(
        normalized_sympy=lexical[len(prefix) : -len(f", {marker})")],
        normalized_latex=render(expression).latex,
    )


def _verify_candidate(
    candidate: _CandidateComputation,
    request: AnalysisRequest,
    computed: RetainedComputation,
    context: WorkContext,
    reasoning: ReasoningContext | None,
    budget: _OptimizationBudget,
    analyzer: _RetainedAnalyzer,
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

    try:
        replay = _replay_candidate(candidate, request, computed, analyzer=analyzer)
    except ValidationError:
        return _Rejected("complete candidate exceeds ordinary request bounds")
    complete, replayed = replay.request, replay.computed
    if isinstance(replayed, AnalysisFailure):
        return _Rejected("complete candidate does not pass ordinary analysis")
    expansion_budget = ExpansionBudget(remaining=MAX_OPTIMIZATION_TRANSFORM_NODES)
    reserved: set[str] = set()
    for _target, expression, _indices, _domains in _target_inputs(computed):
        reserved.update(_all_symbol_names(expression))
    answers: list[QueryAnswer] = []

    def algorithmic_answer(
        target: str, original: Expression, proposed: Expression
    ) -> QueryAnswer | None:
        if candidate.kind != "finite_polynomial_sum_v1" or reasoning is None:
            return None
        parent_output = retained_output(computed, target)
        checked = derive_checked_nested_sum(parent_output, reasoning)
        occurrence = candidate.occurrences[0] if len(candidate.occurrences) == 1 else None
        if (
            not isinstance(checked, CheckedNestedSumResult)
            or occurrence is None
            or original != parent_output
            or occurrence.path != checked.path
            or occurrence.expression != checked.original
            or proposed != _replace_paths(parent_output, (checked.path,), checked.candidate)
            or render(retained_output(replayed, target)).sympy != render(proposed).sympy
        ):
            return QueryAnswer(
                conclusion="unresolved",
                blockers=("algorithmic identity correlation failed",),
            )
        return QueryAnswer(
            conclusion=(
                "proved_under_assumptions" if checked.conditions or checked.uses else "proved"
            ),
            conditions=checked.conditions,
            assumptions_used=checked.uses,
            evidence=IdentityEvidence(
                statement=(
                    "independently checked finite-polynomial Sum antidifference "
                    "and inclusive boundaries"
                )
            ),
        )

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
            checked_answer = algorithmic_answer(target, _original, _proposed)
            answer = (
                checked_answer
                if checked_answer is not None
                else equivalence_answer(original_expanded, expanded, reasoning)
            )
            normalized_equal = False
            if checked_answer is None and answer.conclusion not in {
                "proved",
                "proved_under_assumptions",
            }:
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
                expression=(
                    _intermediate_interpretation(candidate.intermediate_expression)
                    if computed.expression is not None or candidate.intermediate_scope.binders
                    else _interpretation(candidate.intermediate_expression)
                ),
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
            proposed=(
                _intermediate_interpretation(proposed_expression)
                if candidate.intermediate_name is not None
                and (
                    computed.expression is not None
                    or (
                        candidate.intermediate_scope is not None
                        and candidate.intermediate_scope.binders
                    )
                )
                else _interpretation(proposed_expression)
            ),
        )
        for target_name, original_expression, proposed_expression in raw_transformations
    )
    evidence = IdentityEvidence(
        statement=(
            "independently checked finite-polynomial Sum antidifference and inclusive boundaries"
            if candidate.kind == "finite_polynomial_sum_v1"
            else "checked exact symbolic equivalence for every transformed retained output"
        )
    )
    suggestion = OptimizationSuggestion(
        kind=candidate.kind,
        tier=OPTIMIZATION_FAMILY_TIERS[candidate.kind],
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


def _qualifications_compatible(conditions: tuple[str, ...], request: AnalysisRequest) -> bool:
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
    analyzer: _RetainedAnalyzer,
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

    # Algorithmic identities are not delegated to the rational-equivalence seam.
    # Rederive each identity from its owning pre-step state, correlate its child,
    # then independently derive the corresponding root identity used by the final proof.
    root_algorithmic: dict[str, CheckedNestedSumResult] = {}
    algorithmic_conditions: list[str] = []
    algorithmic_uses: list[RelationshipUse] = []
    parent_computed = root

    for step, child_request in trace:
        child_computed = _replay_request(child_request, analyzer=analyzer).computed
        if isinstance(child_computed, AnalysisFailure):
            return _Rejected("algorithmic final replay failed")
        if step.kind == "finite_polynomial_sum_v1":
            if len(step.transformations) != 1:
                return _Rejected("algorithmic identity has invalid topology")
            transformation = step.transformations[0]
            target = transformation.target.name or "expression"
            parent_output = (
                parent_computed.expression
                if target == "expression"
                else next(
                    item.formula.right for item in parent_computed.equations if item.name == target
                )
            )
            child_output = (
                child_computed.expression
                if target == "expression"
                else next(
                    item.formula.right for item in child_computed.equations if item.name == target
                )
            )
            assert parent_output is not None and child_output is not None
            checked = derive_checked_nested_sum(parent_output, reasoning)
            if not isinstance(checked, CheckedNestedSumResult):
                return _Rejected("algorithmic identity cannot be independently rederived")
            expected = _replace_paths(parent_output, (checked.path,), checked.candidate)
            occurrence = transformation.occurrences[0]
            if (
                occurrence.path != checked.path
                or transformation.original != _interpretation(parent_output)
                or transformation.proposed != _interpretation(expected)
                or render(child_output).sympy != render(expected).sympy
                or step.conditions != checked.conditions
                or step.assumptions_used != checked.uses
            ):
                return _Rejected("algorithmic identity provenance is not correlated")
            root_output = (
                root.expression
                if target == "expression"
                else next(item.formula.right for item in root.equations if item.name == target)
            )
            assert root_output is not None
            root_checked = derive_checked_nested_sum(root_output, reasoning)
            if not isinstance(root_checked, CheckedNestedSumResult):
                return _Rejected("original algorithmic identity cannot be independently rederived")
            root_algorithmic[target] = root_checked
            algorithmic_conditions.extend(checked.conditions)
            algorithmic_uses.extend(checked.uses)
        parent_computed = child_computed

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
            proof_original = original
            if target in root_algorithmic:
                checked = root_algorithmic[target]
                proof_original = _replace_paths(original, (checked.path,), checked.candidate)
            left = MappedOutputExpander(
                root, ExpansionBudget(remaining=MAX_OPTIMIZATION_TRANSFORM_NODES), set(reserved)
            ).expand(proof_original)
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
                    *algorithmic_conditions,
                    *[item for answer in answers for item in answer.conditions],
                    *relation.conditions,
                )
            )
        )
        assumptions = _unique_uses(
            (
                *[use for step, _candidate in trace for use in step.assumptions_used],
                *algorithmic_uses,
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
