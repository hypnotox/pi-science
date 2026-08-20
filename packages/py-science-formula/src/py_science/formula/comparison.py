"""Bounded direct-Python mathematical candidate comparison."""

from __future__ import annotations

from typing import Literal

from py_science.formula.computation import NamedRelationship, RetainedComputation
from py_science.formula.expressions import (
    Call,
    Equation,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    Relationship,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
)
from py_science.formula.mapped_outputs import (
    ExpansionBudget,
    compare_mapped_outputs,
)
from py_science.formula.models import (
    AnalysisFailure,
    CandidateAnalysisReport,
    CandidateComparisonOutcome,
    CandidateComparisonRequest,
    CandidateComparisonSuccess,
    CandidateOutputComparison,
    CandidateTargetReference,
    CandidateWorkComparison,
    ExpressionTarget,
    Interpretation,
    QueryAnswer,
    SourceReference,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.service import (
    MAX_REQUEST_BYTES,
    MAX_REQUEST_NODES,
    MAX_RESULT_BYTES,
    _analyze_computation,  # pyright: ignore[reportPrivateUsage]
    _complexity_failure,  # pyright: ignore[reportPrivateUsage]
)
from py_science.formula.work import (
    AggregateWorkComparisonInput,
    WorkRenderBudget,
    compare_aggregate_work,
    render_work,
)


def compare_candidates(request: CandidateComparisonRequest) -> CandidateComparisonOutcome:
    """Compare exactly two mapped candidates without changing ordinary analysis."""
    request_failure = _comparison_request_size_failure(request)
    if request_failure is not None:
        return request_failure

    analyzed_items: list[RetainedComputation] = []
    for position, candidate in enumerate(request.candidates):
        analyzed = _analyze_computation(request.analysis_request(candidate))
        if isinstance(analyzed, AnalysisFailure):
            return _prefix_failure(analyzed, f"candidates[{position}]")
        analyzed_items.append(analyzed)
    left, right = analyzed_items

    try:
        reports = (
            _report(request.candidates[0].name, analyzed_items[0]),
            _report(request.candidates[1].name, analyzed_items[1]),
        )
        budget = ExpansionBudget()
        reserved_names = _reserved_names(request, analyzed_items)
        outputs = tuple(
            _compare_output(
                mapping.name,
                mapping.targets,
                left,
                right,
                request,
                budget,
                reserved_names,
            )
            for mapping in request.outputs
        )
        semantic = _semantic_status(outputs)
        work = _work(request, reports, analyzed_items, semantic)
        result = CandidateComparisonSuccess(
            candidates=reports,
            outputs=outputs,
            semantic_status=semantic,
            work_comparison=work,
        )
    except ExpressionTooComplex as error:
        return _complexity_failure(str(error))
    if len(result.model_dump_json().encode("utf-8")) > MAX_RESULT_BYTES:
        return _complexity_failure("candidate comparison result exceeds its size bound")
    return result


def _report(name: str, analyzed: RetainedComputation) -> CandidateAnalysisReport:
    blockers = analyzed.success.direct_work_blockers
    work = (
        None
        if blockers
        else render_work(analyzed.aggregate_analysis.total_work, WorkRenderBudget())
    )
    return CandidateAnalysisReport(
        name=name,
        analysis=analyzed.success,
        aggregate_work=work,
    )


def _compare_output(
    name: str,
    submitted_targets: tuple[CandidateTargetReference, ...],
    left: RetainedComputation,
    right: RetainedComputation,
    request: CandidateComparisonRequest,
    budget: ExpansionBudget,
    reserved_names: set[str],
) -> CandidateOutputComparison:
    by_candidate = {target.candidate: target for target in submitted_targets}
    targets = (
        by_candidate[request.candidates[0].name],
        by_candidate[request.candidates[1].name],
    )
    result = compare_mapped_outputs(
        name,
        targets[0].target,
        targets[1].target,
        left,
        right,
        budget,
        reserved_names,
        lambda facts: _comparison_reasoning(request, left, facts),
    )
    return _output(
        name,
        targets,
        result.interface_status,
        result.expanded_interpretations,
        result.answer,
    )


def _comparison_reasoning(
    request: CandidateComparisonRequest,
    analyzed: RetainedComputation,
    domain_facts: tuple[NamedRelationship, ...],
) -> ReasoningContext | None:
    try:
        return ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            analyzed.knowledge.definitions,
            (*analyzed.knowledge.assumptions, *domain_facts),
        )
    except ExpressionTooComplex:
        return None


def _output(
    name: str,
    targets: tuple[CandidateTargetReference, CandidateTargetReference],
    interface: Literal["compatible", "incompatible", "unresolved"],
    expanded: tuple[Interpretation, Interpretation] | None,
    answer: QueryAnswer,
) -> CandidateOutputComparison:
    return CandidateOutputComparison(
        name=name,
        targets=targets,
        interface_status=interface,
        expanded_interpretations=expanded,
        answer=answer.model_copy(
            update={"check": None, "derived_candidates": (), "constraint_uses": ()}
        ),
    )


def _semantic_status(
    outputs: tuple[CandidateOutputComparison, ...],
) -> Literal[
    "proved_equal", "proved_equal_under_assumptions", "disproved", "unresolved"
]:
    conclusions = {item.answer.conclusion for item in outputs}
    if "disproved" in conclusions:
        return "disproved"
    if conclusions & {"unresolved", "inapplicable"}:
        return "unresolved"
    if "proved_under_assumptions" in conclusions:
        return "proved_equal_under_assumptions"
    return "proved_equal"


def _work(
    request: CandidateComparisonRequest,
    reports: tuple[CandidateAnalysisReport, CandidateAnalysisReport],
    analyzed: list[RetainedComputation],
    semantic: Literal[
        "proved_equal", "proved_equal_under_assumptions", "disproved", "unresolved"
    ],
) -> CandidateWorkComparison:
    candidate_names = (reports[0].name, reports[1].name)
    works = (reports[0].aggregate_work, reports[1].aggregate_work)
    operands = tuple(
        AggregateWorkComparisonInput(
            work=item.aggregate_analysis.total_work,
            available=report.aggregate_work is not None,
            unknown_costs=item.aggregate_analysis.unknown_costs,
            direct_work_blockers=item.aggregate_analysis.direct_work_blockers,
        )
        for report, item in zip(reports, analyzed, strict=True)
    )
    relation = compare_aggregate_work(
        operands[0],
        operands[1],
        _comparison_reasoning(request, analyzed[0], ()),
        semantic_established=semantic not in {"disproved", "unresolved"},
    )
    return CandidateWorkComparison(
        candidate_names=candidate_names,
        candidate_works=works,
        delta=(
            render_work(relation.delta, WorkRenderBudget())
            if relation.delta is not None
            else None
        ),
        status=relation.status,
        conditions=relation.conditions,
        assumptions_used=relation.assumptions_used,
        relevant_unsupported_assumptions=relation.relevant_unsupported_assumptions,
        blockers=relation.blockers,
        evidence=relation.evidence,
    )


def _comparison_request_size_failure(
    request: CandidateComparisonRequest,
) -> AnalysisFailure | None:
    sources: list[str] = []
    mathematical_sources: list[str] = []
    for candidate in request.candidates:
        sources.append(candidate.name)
        if candidate.expression is not None:
            sources.append(candidate.expression)
            mathematical_sources.append(candidate.expression)
        for equation in candidate.equations:
            sources.extend((equation.name, equation.expression))
            mathematical_sources.append(equation.expression)
            for name, domain in equation.domains.items():
                sources.extend((name, domain.lower, domain.upper))
                mathematical_sources.extend((domain.lower, domain.upper))
            for constraint in equation.constraints:
                sources.extend(
                    (constraint.name, constraint.target, constraint.relationship)
                )
                mathematical_sources.append(constraint.relationship)
    for output in request.outputs:
        sources.append(output.name)
        for target in output.targets:
            sources.append(target.candidate)
            if not isinstance(target.target, ExpressionTarget):
                sources.append(target.target.name)
    sources.extend(request.variables)
    for definition in request.functions:
        sources.extend((definition.name, *definition.parameters, definition.body))
        mathematical_sources.append(definition.body)
    for primitive in request.primitive_costs:
        sources.extend((primitive.name, *primitive.parameters, primitive.work))
        mathematical_sources.append(primitive.work)
    for assumption in request.assumptions:
        sources.extend((assumption.name, assumption.relationship))
        mathematical_sources.append(assumption.relationship)
    for definition in request.definitions:
        sources.extend((definition.variable, definition.expression))
        mathematical_sources.append(definition.expression)
    try:
        source_bytes = sum(len(source.encode("utf-8")) for source in sources)
    except UnicodeEncodeError:
        return _complexity_failure("candidate comparison source is not valid UTF-8")
    if source_bytes > MAX_REQUEST_BYTES:
        return _complexity_failure("candidate comparison request exceeds its byte bound")

    nodes = 0
    for source in mathematical_sources:
        parsed = parse_expression(source)
        if isinstance(parsed, ParseFailure):
            continue
        if isinstance(parsed, (Equation, Relationship)):
            nodes += (
                expression_node_count(parsed.left)
                + expression_node_count(parsed.right)
                + 1
            )
        else:
            nodes += expression_node_count(parsed)
        if nodes > MAX_REQUEST_NODES:
            return _complexity_failure(
                "candidate comparison mathematical structure is too complex"
            )
    return None


def _prefix_failure(failure: AnalysisFailure, prefix: str) -> AnalysisFailure:
    source = failure.error.source
    path = prefix if source is None else f"{prefix}.{source.path}"
    return failure.model_copy(
        update={
            "error": failure.error.model_copy(
                update={
                    "source": SourceReference(
                        path=path,
                        span=source.span if source is not None else None,
                        excerpt=source.excerpt if source is not None else None,
                    )
                }
            )
        }
    )


def _reserved_names(
    request: CandidateComparisonRequest,
    analyzed: list[RetainedComputation],
) -> set[str]:
    names = set(request.variables)
    for item in analyzed:
        names.update(item.producers)
        if item.expression is not None:
            names.update(_expression_names(item.expression))
        for equation in item.equations:
            names.update(_expression_names(equation.formula.right))
            names.update(equation.domains)
    return names


def _expression_names(value: Expression) -> set[str]:
    names: set[str] = set()
    if isinstance(value, (Symbol, IndexedValue, Call)):
        names.add(value.name)
    elif isinstance(value, Sum):
        names.add(value.index)
    for child in expression_children(value):
        names.update(_expression_names(child))
    return names
