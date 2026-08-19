"""Bounded direct-Python mathematical candidate comparison."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from py_science.formula.domains import OutputDomain
from py_science.formula.equivalence import equivalence_answer
from py_science.formula.exact_values import parse_exact_scalar
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    IntegerLiteral,
    RationalLiteral,
    Relationship,
    RelationshipOperator,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
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
    IdentityEvidence,
    Interpretation,
    PropertyEvidence,
    QueryAnswer,
    SignPropertyCheck,
    SourceReference,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.properties import property_answer
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.service import (
    MAX_REQUEST_BYTES,
    MAX_REQUEST_NODES,
    MAX_RESULT_BYTES,
    NamedRelationship,
    _analyze_computation,  # pyright: ignore[reportPrivateUsage]
    _AnalyzedComputation,  # pyright: ignore[reportPrivateUsage]
    _complexity_failure,  # pyright: ignore[reportPrivateUsage]
)
from py_science.formula.sympy_backend import NormalizationError, render
from py_science.formula.work import (
    WorkRenderBudget,
    render_work,
    simplify_constants,
)

MAX_COMPARISON_EXPANSION_NODES = 16_384


@dataclass(slots=True)
class _ExpansionBudget:
    remaining: int = MAX_COMPARISON_EXPANSION_NODES

    def consume(self, nodes: int = 1) -> None:
        self.remaining -= nodes
        if self.remaining < 0:
            raise ExpressionTooComplex(
                "comparison expansion exceeds its aggregate node bound"
            )


@dataclass(frozen=True, slots=True)
class _Operand:
    value: Expression
    binders: tuple[str, ...] | None
    domains: tuple[OutputDomain, ...]


class _Expander:
    def __init__(
        self,
        analyzed: _AnalyzedComputation,
        budget: _ExpansionBudget,
        reserved_names: set[str],
    ) -> None:
        self.analyzed = analyzed
        self.budget = budget
        self.reserved_names = set(reserved_names)
        self.fresh_position = 0

    def expand(
        self,
        value: Expression,
        replacements: Mapping[str, Expression] | None = None,
    ) -> Expression:
        return self._visit(value, replacements or {}, frozenset(), ())

    def _visit(
        self,
        value: Expression,
        replacements: Mapping[str, Expression],
        bound: frozenset[str],
        producer_stack: tuple[str, ...],
    ) -> Expression:
        self.budget.consume()
        if isinstance(value, Symbol):
            if value.name in replacements and value.name not in bound:
                return self._visit(replacements[value.name], {}, bound, producer_stack)
            producer = self.analyzed.producers.get(value.name)
            if producer is not None and producer.arity == 0 and value.name not in bound:
                if producer.equation_name in producer_stack:
                    raise ExpressionTooComplex("comparison producer expansion is recursive")
                equation = self._producer_equation(producer.equation_name)
                return self._visit(
                    equation.formula.right,
                    {},
                    bound,
                    (*producer_stack, producer.equation_name),
                )
            return value
        if isinstance(value, IndexedValue):
            indices = tuple(
                self._visit(index, replacements, bound, producer_stack)
                for index in value.indices
            )
            producer = self.analyzed.producers.get(value.name)
            if producer is None:
                return IndexedValue(value.name, indices)
            if producer.arity != len(indices):
                raise ExpressionTooComplex("comparison producer arity changed after validation")
            if producer.equation_name in producer_stack:
                raise ExpressionTooComplex("comparison producer expansion is recursive")
            equation = self._producer_equation(producer.equation_name)
            lhs = equation.formula.left
            if not isinstance(lhs, IndexedValue):
                raise ExpressionTooComplex("comparison producer interface is inconsistent")
            formal_symbols = tuple(
                index for index in lhs.indices if isinstance(index, Symbol)
            )
            if len(formal_symbols) != len(lhs.indices):
                raise ExpressionTooComplex("comparison producer binders are inconsistent")
            formal = tuple(index.name for index in formal_symbols)
            return self._visit(
                equation.formula.right,
                dict(zip(formal, indices, strict=True)),
                bound,
                (*producer_stack, producer.equation_name),
            )
        if isinstance(value, Call):
            return Call(
                value.name,
                tuple(
                    self._visit(argument, replacements, bound, producer_stack)
                    for argument in value.arguments
                ),
            )
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator,
                self._visit(value.left, replacements, bound, producer_stack),
                self._visit(value.right, replacements, bound, producer_stack),
            )
        if isinstance(value, Sum):
            lower = self._visit(value.lower, replacements, bound, producer_stack)
            upper = self._visit(value.upper, replacements, bound, producer_stack)
            fresh = self._fresh_sum_name()
            renamed_body = _rename_bound(value.body, value.index, fresh)
            inner_replacements = {
                name: replacement
                for name, replacement in replacements.items()
                if name != value.index
            }
            body = self._visit(
                renamed_body,
                inner_replacements,
                bound | {fresh},
                producer_stack,
            )
            return Sum(body, fresh, lower, upper)
        return value

    def _producer_equation(self, name: str):
        return next(equation for equation in self.analyzed.equations if equation.name == name)

    def _fresh_sum_name(self) -> str:
        while True:
            name = f"comparison_sum_{self.fresh_position}"
            self.fresh_position += 1
            if name not in self.reserved_names:
                self.reserved_names.add(name)
                return name


def compare_candidates(request: CandidateComparisonRequest) -> CandidateComparisonOutcome:
    """Compare exactly two mapped candidates without changing ordinary analysis."""
    request_failure = _comparison_request_size_failure(request)
    if request_failure is not None:
        return request_failure

    analyzed_items: list[_AnalyzedComputation] = []
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
        budget = _ExpansionBudget()
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


def _report(name: str, analyzed: _AnalyzedComputation) -> CandidateAnalysisReport:
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
    left: _AnalyzedComputation,
    right: _AnalyzedComputation,
    request: CandidateComparisonRequest,
    budget: _ExpansionBudget,
    reserved_names: set[str],
) -> CandidateOutputComparison:
    by_candidate = {target.candidate: target for target in submitted_targets}
    targets = (
        by_candidate[request.candidates[0].name],
        by_candidate[request.candidates[1].name],
    )
    operands: list[_Operand] = []
    for target, analyzed in zip(targets, (left, right), strict=True):
        operand, blocker = _target_operand(target, analyzed)
        if operand is None:
            return _output(
                name,
                targets,
                "incompatible",
                None,
                QueryAnswer(conclusion="inapplicable", blockers=(blocker,)),
            )
        operands.append(operand)
    left_operand, right_operand = operands
    if (left_operand.binders is None) != (right_operand.binders is None):
        return _incompatible(
            name,
            targets,
            "mapped outputs have incompatible scalar and indexed interfaces",
        )
    if (
        left_operand.binders is not None
        and right_operand.binders is not None
        and len(left_operand.binders) != len(right_operand.binders)
    ):
        return _incompatible(
            name,
            targets,
            "mapped indexed outputs have different arity",
        )

    canonical = _canonical_indices(
        len(left_operand.binders or ()), reserved_names
    )
    left_expander = _Expander(left, budget, reserved_names)
    right_expander = _Expander(right, budget, reserved_names)
    domain_facts: tuple[NamedRelationship, ...] = ()
    interface_answers: tuple[QueryAnswer, ...] = ()
    if left_operand.binders is not None and right_operand.binders is not None:
        interface = _compare_domains(
            name,
            targets,
            left_operand,
            right_operand,
            canonical,
            left_expander,
            right_expander,
            request,
            left,
        )
        if isinstance(interface, CandidateOutputComparison):
            return interface
        domain_facts, interface_answers = interface

    try:
        left_value = left_expander.expand(
            left_operand.value,
            dict(
                zip(
                    left_operand.binders or (),
                    (Symbol(index) for index in canonical),
                    strict=True,
                )
            ),
        )
        right_value = right_expander.expand(
            right_operand.value,
            dict(
                zip(
                    right_operand.binders or (),
                    (Symbol(index) for index in canonical),
                    strict=True,
                )
            ),
        )
        reasoning = _comparison_reasoning(request, left, domain_facts)
        answer = (
            QueryAnswer(
                conclusion="proved",
                evidence=IdentityEvidence(statement="expanded operands are structurally identical"),
            )
            if left_value == right_value
            else equivalence_answer(left_value, right_value, reasoning)
        )
        answer = _merge_interface_qualification(answer, interface_answers)
        left_rendered = render(left_value)
        right_rendered = render(right_value)
    except ExpressionTooComplex as error:
        return _output(
            name,
            targets,
            "compatible",
            None,
            QueryAnswer(conclusion="unresolved", blockers=(str(error),)),
        )
    except NormalizationError:
        return _output(
            name,
            targets,
            "compatible",
            None,
            QueryAnswer(
                conclusion="unresolved",
                blockers=("expanded mapped output cannot be normalized",),
            ),
        )
    interpretations = (
        Interpretation(
            normalized_sympy=left_rendered.sympy,
            normalized_latex=left_rendered.latex,
        ),
        Interpretation(
            normalized_sympy=right_rendered.sympy,
            normalized_latex=right_rendered.latex,
        ),
    )
    return _output(name, targets, "compatible", interpretations, answer)


def _compare_domains(
    name: str,
    targets: tuple[CandidateTargetReference, CandidateTargetReference],
    left: _Operand,
    right: _Operand,
    canonical: tuple[str, ...],
    left_expander: _Expander,
    right_expander: _Expander,
    request: CandidateComparisonRequest,
    analyzed: _AnalyzedComputation,
) -> (
    tuple[tuple[NamedRelationship, ...], tuple[QueryAnswer, ...]]
    | CandidateOutputComparison
):
    assert left.binders is not None and right.binders is not None
    left_by_name = {domain.index: domain for domain in left.domains}
    right_by_name = {domain.index: domain for domain in right.domains}
    left_replacements = dict(
        zip(left.binders, (Symbol(index) for index in canonical), strict=True)
    )
    right_replacements = dict(
        zip(right.binders, (Symbol(index) for index in canonical), strict=True)
    )
    facts: list[NamedRelationship] = []
    answers: list[QueryAnswer] = []
    reasoning = _comparison_reasoning(request, analyzed, ())
    for position, (left_name, right_name, canonical_name) in enumerate(
        zip(left.binders, right.binders, canonical, strict=True)
    ):
        left_domain = left_by_name[left_name]
        right_domain = right_by_name[right_name]
        aligned_left = (
            left_expander.expand(left_domain.lower, left_replacements),
            left_expander.expand(left_domain.upper, left_replacements),
        )
        aligned_right = (
            right_expander.expand(right_domain.lower, right_replacements),
            right_expander.expand(right_domain.upper, right_replacements),
        )
        for endpoint, left_bound, right_bound in zip(
            ("lower", "upper"), aligned_left, aligned_right, strict=True
        ):
            answer = (
                QueryAnswer(
                    conclusion="proved",
                    evidence=IdentityEvidence(statement="aligned domain bounds are identical"),
                )
                if left_bound == right_bound
                else equivalence_answer(left_bound, right_bound, reasoning)
            )
            if answer.conclusion == "disproved":
                return _incompatible(
                    name,
                    targets,
                    f"mapped output {endpoint} domains differ at position {position}",
                )
            if answer.conclusion not in {"proved", "proved_under_assumptions"}:
                blockers = answer.blockers or (
                    f"mapped output {endpoint} domain equality is unproved",
                )
                return _output(
                    name,
                    targets,
                    "unresolved",
                    None,
                    QueryAnswer(conclusion="unresolved", blockers=blockers),
                )
            answers.append(answer)
        lower, upper = aligned_left
        facts.extend(
            (
                NamedRelationship(
                    name=f"comparison:{name}:{position}:lower",
                    source=f"{canonical_name} >= {render(lower).sympy}",
                    value=Relationship(
                        RelationshipOperator.GREATER_EQUAL,
                        Symbol(canonical_name),
                        lower,
                    ),
                ),
                NamedRelationship(
                    name=f"comparison:{name}:{position}:upper",
                    source=f"{canonical_name} <= {render(upper).sympy}",
                    value=Relationship(
                        RelationshipOperator.LESS_EQUAL,
                        Symbol(canonical_name),
                        upper,
                    ),
                ),
            )
        )
    return tuple(facts), tuple(answers)


def _comparison_reasoning(
    request: CandidateComparisonRequest,
    analyzed: _AnalyzedComputation,
    domain_facts: tuple[NamedRelationship, ...],
) -> ReasoningContext | None:
    try:
        return ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            analyzed.knowledge.definitions,
            (*analyzed.knowledge.assumptions, *domain_facts),
        )
    except (ExpressionTooComplex, RuntimeError):
        return None


def _merge_interface_qualification(
    answer: QueryAnswer, interface_answers: tuple[QueryAnswer, ...]
) -> QueryAnswer:
    conditions = tuple(
        dict.fromkeys(
            condition
            for item in (*interface_answers, answer)
            for condition in item.conditions
        )
    )
    uses = tuple(
        {
            (use.name, use.relationship): use
            for item in (*interface_answers, answer)
            for use in item.assumptions_used
        }.values()
    )
    unsupported = tuple(
        dict.fromkeys(
            value
            for item in (*interface_answers, answer)
            for value in item.relevant_unsupported_assumptions
        )
    )
    conclusion = answer.conclusion
    if conclusion == "proved" and (conditions or uses):
        conclusion = "proved_under_assumptions"
    return answer.model_copy(
        update={
            "check": None,
            "conclusion": conclusion,
            "conditions": conditions,
            "assumptions_used": uses,
            "relevant_unsupported_assumptions": unsupported,
            "derived_candidates": (),
            "constraint_uses": (),
        }
    )


def _target_operand(
    reference: CandidateTargetReference,
    analyzed: _AnalyzedComputation,
) -> tuple[_Operand | None, str]:
    target = reference.target
    if isinstance(target, ExpressionTarget):
        if analyzed.expression is None:
            return None, "expression target requires an expression candidate"
        return _Operand(analyzed.expression, None, ()), ""
    equation = next(
        (item for item in analyzed.equations if item.name == target.name), None
    )
    if equation is None:
        return None, "mapped equation target is unknown"
    lhs = equation.formula.left
    if isinstance(lhs, IndexedValue):
        binder_symbols = tuple(
            index for index in lhs.indices if isinstance(index, Symbol)
        )
        if len(binder_symbols) != len(lhs.indices):
            return None, "mapped equation binders are inconsistent"
        binders = tuple(index.name for index in binder_symbols)
        domains = tuple(
            next(domain for domain in equation.output_domains if domain.index == binder)
            for binder in binders
        )
        return _Operand(equation.formula.right, binders, domains), ""
    return _Operand(equation.formula.right, None, ()), ""


def _incompatible(
    name: str,
    targets: tuple[CandidateTargetReference, CandidateTargetReference],
    blocker: str,
) -> CandidateOutputComparison:
    return _output(
        name,
        targets,
        "incompatible",
        None,
        QueryAnswer(conclusion="inapplicable", blockers=(blocker,)),
    )


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
    analyzed: list[_AnalyzedComputation],
    semantic: Literal[
        "proved_equal", "proved_equal_under_assumptions", "disproved", "unresolved"
    ],
) -> CandidateWorkComparison:
    candidate_names = (reports[0].name, reports[1].name)
    works = (reports[0].aggregate_work, reports[1].aggregate_work)
    delta_expression: Expression | None = None
    delta: str | None = None
    if works[0] is not None and works[1] is not None:
        delta_expression = simplify_constants(
            BinaryExpression(
                BinaryOperator.SUBTRACT,
                analyzed[1].aggregate_analysis.total_work,
                analyzed[0].aggregate_analysis.total_work,
            )
        )
        delta = render_work(delta_expression, WorkRenderBudget())
    if semantic in {"disproved", "unresolved"}:
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            delta=delta,
            status="not_comparable",
            blockers=("mapped output semantics are not established",),
        )
    if delta_expression is None or delta is None:
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            status="unresolved",
            blockers=("candidate aggregate direct work is unavailable",),
        )
    unknown_costs = sorted(
        set(analyzed[0].aggregate_analysis.unknown_costs)
        | set(analyzed[1].aggregate_analysis.unknown_costs)
    )
    if unknown_costs:
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            delta=delta,
            status="unresolved",
            blockers=("unknown primitive costs: " + ", ".join(unknown_costs),),
        )

    reasoning = _comparison_reasoning(request, analyzed[0], ())
    zero_answer = equivalence_answer(delta_expression, IntegerLiteral(0), reasoning)
    if zero_answer.conclusion in {"proved", "proved_under_assumptions"}:
        evidence = zero_answer.evidence
        if not isinstance(evidence, IdentityEvidence):
            evidence = IdentityEvidence(statement="aggregate work difference is zero")
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            delta=delta,
            status="equal",
            conditions=zero_answer.conditions,
            assumptions_used=zero_answer.assumptions_used,
            relevant_unsupported_assumptions=zero_answer.relevant_unsupported_assumptions,
            evidence=evidence,
        )

    constant_sign = _constant_sign(delta_expression, delta)
    if constant_sign is not None:
        constant_status: Literal["first_lower", "second_lower"] = (
            "first_lower" if constant_sign > 0 else "second_lower"
        )
        label = "positive" if constant_sign > 0 else "negative"
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            delta=delta,
            status=constant_status,
            evidence=PropertyEvidence(
                value="exact constant aggregate-work sign",
                intervals=(f"all values: {label}",),
            ),
        )

    sign_answer = property_answer(delta_expression, SignPropertyCheck(), reasoning)
    if (
        sign_answer.conclusion not in {"proved", "proved_under_assumptions"}
        or not isinstance(sign_answer.evidence, PropertyEvidence)
    ):
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            delta=delta,
            status="unresolved",
            conditions=sign_answer.conditions,
            assumptions_used=sign_answer.assumptions_used,
            relevant_unsupported_assumptions=sign_answer.relevant_unsupported_assumptions,
            blockers=sign_answer.blockers
            or ("exact aggregate-work sign is unsupported",),
        )
    signs = {
        interval.rsplit(": ", 1)[-1]
        for interval in sign_answer.evidence.intervals
        if interval.rsplit(": ", 1)[-1] in {"positive", "negative"}
    }
    chart_status: Literal[
        "first_lower", "second_lower", "crossover", "unresolved"
    ] = (
        "crossover"
        if signs == {"positive", "negative"}
        else "first_lower"
        if signs == {"positive"}
        else "second_lower"
        if signs == {"negative"}
        else "unresolved"
    )
    if chart_status == "unresolved":
        return CandidateWorkComparison(
            candidate_names=candidate_names,
            candidate_works=works,
            delta=delta,
            status=chart_status,
            conditions=sign_answer.conditions,
            assumptions_used=sign_answer.assumptions_used,
            relevant_unsupported_assumptions=sign_answer.relevant_unsupported_assumptions,
            blockers=("exact aggregate-work sign chart has no decisive intervals",),
        )
    return CandidateWorkComparison(
        candidate_names=candidate_names,
        candidate_works=works,
        delta=delta,
        status=chart_status,
        conditions=sign_answer.conditions,
        assumptions_used=sign_answer.assumptions_used,
        relevant_unsupported_assumptions=sign_answer.relevant_unsupported_assumptions,
        evidence=sign_answer.evidence,
    )


def _constant_sign(expression: Expression, rendered: str) -> int | None:
    if isinstance(expression, IntegerLiteral):
        return (expression.value > 0) - (expression.value < 0)
    if isinstance(expression, RationalLiteral):
        return (expression.numerator > 0) - (expression.numerator < 0)
    exact = parse_exact_scalar(rendered)
    if exact is None:
        return None
    return (exact.numerator > 0) - (exact.numerator < 0)


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
    analyzed: list[_AnalyzedComputation],
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


def _canonical_indices(arity: int, reserved_names: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    position = 0
    while len(result) < arity:
        name = f"comparison_index_{position}"
        position += 1
        if name not in reserved_names:
            reserved_names.add(name)
            result.append(name)
    return tuple(result)


def _rename_bound(value: Expression, old: str, new: str) -> Expression:
    if isinstance(value, Symbol):
        return Symbol(new) if value.name == old else value
    if isinstance(value, IndexedValue):
        return IndexedValue(
            value.name,
            tuple(_rename_bound(index, old, new) for index in value.indices),
        )
    if isinstance(value, Call):
        return Call(
            value.name,
            tuple(_rename_bound(argument, old, new) for argument in value.arguments),
        )
    if isinstance(value, BinaryExpression):
        return BinaryExpression(
            value.operator,
            _rename_bound(value.left, old, new),
            _rename_bound(value.right, old, new),
        )
    if isinstance(value, Sum):
        lower = _rename_bound(value.lower, old, new)
        upper = _rename_bound(value.upper, old, new)
        body = value.body if value.index == old else _rename_bound(value.body, old, new)
        return Sum(body, value.index, lower, upper)
    return value
