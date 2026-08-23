# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Bounded traversal, fair admission, and optimization report orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from functools import cmp_to_key

from py_science.formula._analysis.occurrences import (
    _detect_occurrences,
    _Occurrence,
    _TraversalExhausted,
)
from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.expressions import Expression, ExpressionTooComplex, expression_node_count
from py_science.formula.models import (
    AnalysisFailure,
    AnalysisRequest,
    OptimizationKind,
    OptimizationOrdering,
    OptimizationReport,
    OptimizationSuggestion,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.work import WorkContext, project_optimization_objective

from .budgets import (
    MAX_OPTIMIZATION_COMPLETE_REANALYSES,
    MAX_OPTIMIZATION_PROOF_NODES,
    MAX_OPTIMIZATION_TRANSFORM_NODES,
    _BudgetExhausted,
    _default_budget_config,
    _OptimizationBudget,
    _OptimizationBudgetConfig,
    _WholeTransitionBudget,
)
from .candidates import _CandidateComputation, _CandidateDescriptor, _generated_name, _target_inputs
from .canonical import _canonical_state_key, _trace_key
from .diagnostics import _OutcomeAccounting
from .families import (
    call_reuse,
    cross_equation_sharing,
    factoring,
    finite_polynomial_sum,
    horner,
    invariant_hoisting,
    redundant_operations,
    repeated_structure,
)
from .objectives import _accepted_order, _adjacent_ordering_relation, _suggestion_order
from .plans import project_plan
from .verifier import (
    _Accepted,
    _as_work,
    _Exhausted,
    _original_final_suggestion,
    _reasoning,
    _Rejected,
    _verify_candidate,
)

type _RetainedAnalyzer = Callable[[AnalysisRequest], RetainedComputation | AnalysisFailure]

_FAMILY_ORDER: tuple[OptimizationKind, ...] = (
    "repeated_subexpression",
    "repeated_call",
    "reciprocal_reuse",
    "factoring",
    "redundant_operation_removal",
    "iterator_invariant_hoisting",
    "cross_equation_sharing",
    "horner",
    "finite_polynomial_sum_v1",
)


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
    *,
    algorithmic_enabled: bool = False,
    reasoning: ReasoningContext | None = None,
    accounting: _OutcomeAccounting | None = None,
) -> tuple[dict[OptimizationKind, tuple[_CandidateDescriptor, ...]], tuple[str, ...]]:
    """Traverse each retained target once; families receive neutral occurrence facts."""
    collector = collector or _RetainedLaneCollector(budget)
    qualifications: list[str] = []
    generated_name = _generated_name(computed)
    occurrences_by_target: dict[str, tuple[_Occurrence, ...]] = {}

    def append(descriptor: _CandidateDescriptor) -> None:
        collector.add((*lane_prefix, descriptor.kind), descriptor)
        if accounting is not None:
            accounting.proposals += 1

    try:
        for target, expression, output_indices, output_domains in sorted(
            _target_inputs(computed), key=lambda item: item[0]
        ):
            if accounting is not None:
                accounting.generation_observed()
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
                raise _BudgetExhausted(
                    budget.resource("inspected nodes"),
                    budget.inspections + expression_node_count(expression),
                    budget.config.inspections,
                ) from None
            budget.inspect(max(1, expression_node_count(expression)))
            occurrences_by_target[target] = occurrences
            for descriptor in repeated_structure.propose(
                target, expression, occurrences, generated_name
            ):
                append(descriptor)
            for descriptor in call_reuse.propose(target, expression, occurrences, generated_name):
                append(descriptor)
            if algorithmic_enabled and reasoning is not None:
                for descriptor in finite_polynomial_sum.propose(
                    target, expression, occurrences, reasoning
                ):
                    append(descriptor)
            for occurrence in occurrences:
                for descriptor in redundant_operations.propose(target, expression, occurrence):
                    append(descriptor)
                for descriptor in factoring.propose(target, expression, occurrence):
                    append(descriptor)
                budget.inspect(max(1, expression_node_count(occurrence.expression)))
                descriptors, family_qualifications = horner.propose(
                    target, expression, occurrence, accounting=accounting
                )
                qualifications.extend(family_qualifications)
                for descriptor in descriptors:
                    append(descriptor)
                for descriptor in invariant_hoisting.propose(
                    target, expression, occurrence, generated_name
                ):
                    append(descriptor)
        try:
            sharing_descriptors = cross_equation_sharing.propose(
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
    *,
    analyzer: _RetainedAnalyzer,
    accounting: _OutcomeAccounting | None = None,
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
    accounting = accounting or _OutcomeAccounting()
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
            computed,
            depth_one_budget,
            root_collector,
            algorithmic_enabled=(
                "finite_polynomial_sum_v1" in request.optimization.enabled_algorithmic_families
            ),
            reasoning=reasoning,
            accounting=accounting,
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
            accounting.transition_verified()
            outcome = _verify_candidate(
                candidate,
                request,
                computed,
                context,
                reasoning,
                depth_one_budget,
                analyzer,
                accounting=accounting,
            )
            if isinstance(outcome, _Exhausted):
                qualifications.append(outcome.reason)
            elif isinstance(outcome, _Rejected):
                accounting.transition_rejected()
            else:
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
                parent.computed,
                depth_two_budget,
                depth_two_collector,
                (parent.canonical_key,),
                algorithmic_enabled=(
                    "finite_polynomial_sum_v1" in request.optimization.enabled_algorithmic_families
                ),
                reasoning=reasoning,
                accounting=accounting,
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
        accounting.transition_verified()
        outcome = _verify_candidate(
            candidate,
            parent.request,
            parent.computed,
            context,
            reasoning,
            depth_two_budget,
            analyzer,
            accounting=accounting,
        )
        if isinstance(outcome, _Exhausted):
            qualifications.append(outcome.reason)
        elif isinstance(outcome, _Rejected):
            accounting.transition_rejected()
        else:
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
        accounting.final_acceptance_observed()
        final = _original_final_suggestion(
            state.trace[-1][0],
            state.trace,
            computed,
            state.computed,
            request,
            reasoning,
            final_budget,
            analyzer,
            accounting=accounting,
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
    plans = tuple(project_plan(item, request, computed) for item in ordered)
    return OptimizationReport(
        requested_limit=limit,
        status="incomplete" if qualifications else "complete",
        suggestions=tuple(item.suggestion for item in ordered),
        plans=plans,
        qualifications=_unique_qualifications(qualifications),
    )
