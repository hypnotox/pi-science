# ruff: noqa: E501
from __future__ import annotations

# pyright: reportPrivateUsage=false
from fractions import Fraction

from py_science.formula._analysis.computation import (
    MAX_COMBINED_RESULT_BYTES,
    MAX_OPTIMIZATION_BYTES,
    MAX_RESULT_BYTES,
    _complexity_failure,
    _constant_value,
    _exact_fraction,
    _invalid,
    _scenario_literal,
    _symbol_names,
    analyze_retained,
)
from py_science.formula._analysis.retained import (
    Knowledge,
    NamedRelationship,
    RetainedComputation,
)
from py_science.formula.expressions import (
    Equation,
    ExpressionTooComplex,
    Relationship,
    RelationshipOperator,
    Symbol,
    substitute,
)
from py_science.formula.models import (
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisRequest,
    AnalysisSuccess,
    AsymptoticQuery,
    AsymptoticResult,
    ClosedFormEvidence,
    ClosedFormResult,
    ConstraintUse,
    DerivedTarget,
    DominanceAnalysisOutcome,
    DominanceAnalysisRequest,
    EquationReport,
    EquationRequest,
    EquationTarget,
    EquivalenceQuery,
    EquivalenceResult,
    ExpressionTarget,
    LimitQuery,
    LimitResult,
    MathematicalDomain,
    OptimizationFailure,
    OptimizationReport,
    OptimizationSuccess,
    OptimizeOutcome,
    OptimizeRequest,
    PropertiesQuery,
    PropertiesResult,
    QueryAnswer,
    QueryResult,
    SourceReference,
)
from py_science.formula.optimization import (
    _optimization_report,  # pyright: ignore[reportPrivateUsage]
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.query import QueryTarget, evaluate_queries
from py_science.formula.reasoning import ReasoningContext

# Characterized private compatibility alias; neutral analysis owns the implementation.
_analyze_computation = analyze_retained


def analyze(request: AnalysisRequest) -> AnalysisOutcome:
    """Analyze one ordinary request; comparison uses the retained private bundle."""
    result = analyze_retained(request)
    if isinstance(result, AnalysisFailure):
        return _bound_result(result)
    outcome: AnalysisOutcome = result.success
    if request.queries:
        outcome = _attach_queries(request, result)
    if isinstance(outcome, AnalysisSuccess):
        try:
            optimization = _optimization_report(request, result, result.work_context, analyzer=analyze_retained)
        except Exception:
            optimization = OptimizationReport(
                requested_limit=request.optimization.max_suggestions,
                status="failed",
                qualifications=("optimization advice failed unexpectedly",),
            )
        outcome = outcome.model_copy(update={"optimization": optimization})
    return _bound_result(outcome)


def _bound_optimization_result(outcome: OptimizationSuccess) -> OptimizationSuccess:
    measured = len(outcome.model_dump_json().encode("utf-8"))
    if measured <= MAX_OPTIMIZATION_BYTES:
        return outcome
    qualification = (
        "optimization result bytes budget exhausted "
        f"(measured {measured}, configured {MAX_OPTIMIZATION_BYTES})"
    )
    for retained in range(len(outcome.plans), -1, -1):
        bounded = outcome.model_copy(
            update={
                "projection_status": "truncated",
                "plans": outcome.plans[:retained],
                "projection_qualifications": (qualification,),
            }
        )
        if len(bounded.model_dump_json().encode("utf-8")) <= MAX_OPTIMIZATION_BYTES:
            return bounded
    raise ValueError("optimization result bound cannot contain its exhaustion diagnostic")


def optimize(request: OptimizeRequest) -> OptimizeOutcome:
    """Run the same bounded Python policy exposed by ordinary advice."""
    try:
        ordinary = AnalysisRequest.model_validate({
            "syntax": request.syntax, "expression": request.expression, "equations": request.equations,
            "variables": request.variables, "functions": request.functions,
            "primitive_costs": request.primitive_costs, "assumptions": request.assumptions,
            "definitions": request.definitions,
            "optimization": {
                "max_suggestions": request.max_plans,
                "objective": request.objective,
                "enabled_algorithmic_families": request.enabled_algorithmic_families,
            },
        })
        computed = analyze_retained(ordinary)
        if isinstance(computed, AnalysisFailure):
            return OptimizationFailure(error=computed.error.message)
        report = _optimization_report(ordinary, computed, computed.work_context, analyzer=analyze_retained)
        if report.status == "failed":
            return OptimizationFailure(error=report.qualifications[0])
        return _bound_optimization_result(
            OptimizationSuccess(
                requested_limit=request.max_plans,
                search_status="incomplete" if report.status == "incomplete" else "complete",
                plans=report.plans,
                qualifications=report.qualifications,
            )
        )
    except Exception:
        # Direct operation failures remain typed and never expose partial candidates.
        return OptimizationFailure(error="optimization operation failed unexpectedly")


def analyze_dominance(request: DominanceAnalysisRequest) -> DominanceAnalysisOutcome:
    """Analyze retained aggregate work once, then delegate dominance policy."""
    from py_science.formula.dominance import analyze_retained as analyze_dominance_retained

    computed = analyze_retained(request.analysis_request())
    if isinstance(computed, AnalysisFailure):
        return computed
    fixed_failure = _dominance_fixed_assumption_failure(request, computed)
    if fixed_failure is not None:
        return fixed_failure
    outcome = analyze_dominance_retained(request, computed)
    if len(outcome.model_dump_json().encode("utf-8")) > MAX_RESULT_BYTES:
        return _complexity_failure("dominance result exceeds its size bound")
    return outcome


def _dominance_fixed_assumption_failure(
    request: DominanceAnalysisRequest, computed: RetainedComputation
) -> AnalysisFailure | None:
    """Reject exact fixed values that contradict checked global reasoning facts."""
    try:
        reasoning = ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            computed.knowledge.definitions,
            computed.knowledge.assumptions,
        )
    except Exception:
        # Dominance policy will return qualified abstention for unavailable
        # supplemental reasoning; do not turn that into a confident rejection.
        return None
    fixed_expressions = {name: _scenario_literal(raw) for name, raw in request.fixed.items()}
    for name, raw in request.fixed.items():
        value = _exact_fraction(raw)
        fact = reasoning.facts.get(name)
        contradicts_fact = fact is not None and (
            (fact.integer and value.denominator != 1)
            or (
                fact.lower is not None
                and (value < fact.lower or (value == fact.lower and fact.lower_strict))
            )
            or (
                fact.upper is not None
                and (value > fact.upper or (value == fact.upper and fact.upper_strict))
            )
        )
        try:
            resolved = substitute(reasoning.apply(Symbol(name)), fixed_expressions, max_nodes=4_096)
        except Exception:
            resolved = Symbol(name)
        replacement_value = _constant_value(resolved)
        if contradicts_fact or (replacement_value is not None and replacement_value != value):
            return _invalid(
                f"fixed substitution contradicts assumptions for {name}",
                source=SourceReference(path=f"fixed.{name}"),
            )
    for assumption in computed.knowledge.assumptions:
        try:
            left = _constant_value(
                substitute(
                    reasoning.apply(assumption.value.left),
                    fixed_expressions,
                    max_nodes=4_096,
                )
            )
            right = _constant_value(
                substitute(
                    reasoning.apply(assumption.value.right),
                    fixed_expressions,
                    max_nodes=4_096,
                )
            )
        except Exception:
            continue
        if (
            left is None
            or right is None
            or _fixed_relationship_holds(assumption.value.operator, left, right)
        ):
            continue
        relevant = sorted(
            (_symbol_names(assumption.value.left) | _symbol_names(assumption.value.right))
            & request.fixed.keys()
        )
        name = relevant[0] if relevant else next(iter(request.fixed))
        return _invalid(
            f"fixed substitution contradicts assumptions for {name}",
            source=SourceReference(path=f"fixed.{name}"),
        )
    return None


def _fixed_relationship_holds(
    operator: RelationshipOperator, left: Fraction, right: Fraction
) -> bool:
    if operator is RelationshipOperator.EQUAL:
        return left == right
    if operator is RelationshipOperator.LESS:
        return left < right
    if operator is RelationshipOperator.LESS_EQUAL:
        return left <= right
    if operator is RelationshipOperator.GREATER:
        return left > right
    return left >= right


def _attach_queries(request: AnalysisRequest, analyzed: RetainedComputation) -> AnalysisOutcome:
    """Evaluate queries in request order, retaining only earlier result provenance."""
    outcome = analyzed.success
    knowledge = analyzed.knowledge
    results: list[QueryResult] = []
    try:
        reasoning = ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            knowledge.definitions,
            knowledge.assumptions,
        )
    except (ExpressionTooComplex, RuntimeError):
        reasoning = None
    for position, query in enumerate(request.queries):
        source: QueryResult | None = None
        report: EquationReport | None = None
        owning: EquationRequest | None = None
        if isinstance(query.target, DerivedTarget):
            assert isinstance(
                query, (EquivalenceQuery, PropertiesQuery, LimitQuery, AsymptoticQuery)
            )
            source = next(result for result in results if result.name == query.target.query)
            target_or_none = _derived_target(query.target, source)
            if target_or_none is None:
                results.append(
                    _compose_derived_qualification(
                        _unavailable_derived_result(query, source), source
                    )
                )
                continue
            target = target_or_none
            if request.expression is None and isinstance(source.target, EquationTarget):
                owning = next(item for item in request.equations if item.name == source.target.name)
                report = next(
                    item
                    for item in outcome.system.equations  # type: ignore[union-attr]
                    if item.name == source.target.name
                )
        elif request.expression is not None:
            parsed = analyzed.expression
            target = (
                QueryTarget(ExpressionTarget(), parsed, outcome.interpretation)
                if parsed is not None
                else None
            )
        else:
            assert query.target is not None
            selected = next(
                (item for item in request.equations if item.name == query.target.name),
                None,
            )
            report = (
                next(
                    (item for item in outcome.system.equations if item.name == query.target.name),
                    None,
                )
                if outcome.system is not None
                else None
            )
            if selected is None or report is None:
                return _invalid(
                    "query target is unknown",
                    source=SourceReference(path=f"queries[{position}].target"),
                )
            parsed = next(
                (item.formula for item in analyzed.equations if item.name == selected.name),
                None,
            )
            target = (
                QueryTarget(query.target, parsed.right, report.interpretation)
                if parsed is not None
                else None
            )
        if target is None:
            return _invalid(
                "query target could not be resolved",
                source=SourceReference(path=f"queries[{position}].target"),
            )
        query_reasoning = reasoning
        if request.expression is None:
            if not isinstance(query.target, DerivedTarget):
                assert query.target is not None
                owning = next(item for item in request.equations if item.name == query.target.name)
            assert owning is not None and report is not None
            # Equation-local facts are deliberately reconstructed only for the
            # submitted equation or its explicit verified derived operand. They
            # never become request-wide solver facts or leak to another equation.
            query_reasoning = _equation_query_reasoning(request, knowledge, owning, report)
        query_reserved_names = frozenset(
            set(request.variables)
            | {item.variable for item in request.definitions}
            | set(analyzed.producers)
            | {index for item in request.equations for index in item.domains}
        )
        evaluated = evaluate_queries(
            (query,), target, query_reasoning, query_reserved_names
        )
        if isinstance(evaluated, AnalysisFailure):
            return evaluated
        result = evaluated[0]
        if owning is not None:
            local_uses = {
                (constraint.name, constraint.relationship) for constraint in owning.constraints
            }
            consumed = tuple(
                ConstraintUse(
                    equation=owning.name,
                    name=constraint.name,
                    target=constraint.target,
                    relationship=constraint.relationship,
                )
                for constraint in owning.constraints
                if any(
                    (use.name, use.relationship) in local_uses
                    and use.name == constraint.name
                    and use.relationship == constraint.relationship
                    for answer in result.answers
                    for use in answer.assumptions_used
                )
            )
            if consumed:
                result = result.model_copy(
                    update={
                        "answers": tuple(
                            answer.model_copy(
                                update={
                                    "assumptions_used": tuple(
                                        relationship
                                        for relationship in answer.assumptions_used
                                        if (relationship.name, relationship.relationship)
                                        not in local_uses
                                    ),
                                    "constraint_uses": tuple(
                                        use
                                        for use in consumed
                                        if any(
                                            relationship.name == use.name
                                            and relationship.relationship == use.relationship
                                            for relationship in answer.assumptions_used
                                        )
                                    ),
                                }
                            )
                            for answer in result.answers
                        )
                    }
                )
        if isinstance(query.target, DerivedTarget):
            assert source is not None
            result = _compose_derived_qualification(result, source)
        results.append(result)
    return outcome.model_copy(update={"queries": tuple(results)})


def _equation_query_reasoning(
    request: AnalysisRequest,
    knowledge: Knowledge,
    equation: EquationRequest,
    report: EquationReport,
) -> ReasoningContext | None:
    """Build one equation's scalar context from analyzer-normalized bounds.

    Local constraints are accepted and normalized exclusively by the output-domain
    policy.  Reintroducing their raw text here would make supported scalar proofs
    depend on a second, narrower relationship parser (notably excluding ``Abs``).
    The normalized bound facts retain each submitted constraint as their source so
    query provenance can report the original request spelling.
    """
    domains = {name: declaration.domain for name, declaration in request.variables.items()}
    domains.update({name: MathematicalDomain.INTEGER for name in equation.domains})
    local: list[NamedRelationship] = []
    effective = {domain.index: domain for domain in report.effective_domains}
    constrained_targets = {constraint.target for constraint in equation.constraints}
    for name, domain in effective.items():
        if name in constrained_targets:
            continue
        lower = parse_expression(domain.lower)
        upper = parse_expression(domain.upper)
        if isinstance(lower, (ParseFailure, Equation, Relationship)) or isinstance(
            upper, (ParseFailure, Equation, Relationship)
        ):
            return None
        local.extend(
            (
                NamedRelationship(
                    f"{equation.name}:{name}:lower",
                    f"{name} >= {domain.lower}",
                    Relationship(RelationshipOperator.GREATER_EQUAL, Symbol(name), lower),
                ),
                NamedRelationship(
                    f"{equation.name}:{name}:upper",
                    f"{name} <= {domain.upper}",
                    Relationship(RelationshipOperator.LESS_EQUAL, Symbol(name), upper),
                ),
            )
        )
    for constraint in equation.constraints:
        domain = effective.get(constraint.target)
        if domain is None:
            return None
        lower = parse_expression(domain.lower)
        upper = parse_expression(domain.upper)
        if isinstance(lower, (ParseFailure, Equation, Relationship)) or isinstance(
            upper, (ParseFailure, Equation, Relationship)
        ):
            return None
        local.extend(
            (
                NamedRelationship(
                    constraint.name,
                    constraint.relationship,
                    Relationship(
                        RelationshipOperator.GREATER_EQUAL, Symbol(constraint.target), lower
                    ),
                ),
                NamedRelationship(
                    constraint.name,
                    constraint.relationship,
                    Relationship(RelationshipOperator.LESS_EQUAL, Symbol(constraint.target), upper),
                ),
            )
        )
    try:
        return ReasoningContext.build(
            domains, knowledge.definitions, (*knowledge.assumptions, *local)
        )
    except (ExpressionTooComplex, RuntimeError):
        return None


def _derived_target(target: DerivedTarget, source: QueryResult) -> QueryTarget | None:
    if not isinstance(source, ClosedFormResult):
        return None
    answer = source.answers[0]
    if (
        answer.conclusion not in {"proved", "proved_under_assumptions"}
        or not isinstance(answer.evidence, ClosedFormEvidence)
        or len(answer.derived_candidates) != 1
    ):
        return None
    parsed = parse_expression(answer.derived_candidates[0].interpretation.normalized_sympy)
    if isinstance(parsed, (ParseFailure, Equation, Relationship)):
        return None
    return QueryTarget(target, parsed, answer.derived_candidates[0].interpretation)


def _unavailable_derived_result(
    query: EquivalenceQuery | PropertiesQuery | LimitQuery | AsymptoticQuery,
    source: QueryResult,
) -> QueryResult:
    assert isinstance(query.target, DerivedTarget)
    blocker = f"derived target source {source.name} concluded {source.answers[0].conclusion}"
    answer = QueryAnswer(conclusion="inapplicable", blockers=(blocker,))
    if isinstance(query, EquivalenceQuery):
        return EquivalenceResult(
            name=query.name,
            target=query.target,
            normalized_target=None,
            summary="derived target is unavailable",
            answers=(answer,),
        )
    if isinstance(query, PropertiesQuery):
        return PropertiesResult(
            name=query.name,
            target=query.target,
            normalized_target=None,
            summary="derived target is unavailable",
            answers=tuple(
                QueryAnswer(check=check, conclusion="inapplicable", blockers=(blocker,))
                for check in query.checks
            ),
        )
    if isinstance(query, LimitQuery):
        return LimitResult(
            name=query.name,
            target=query.target,
            normalized_target=None,
            summary="derived target is unavailable",
            answers=(answer,),
        )
    return AsymptoticResult(
        name=query.name,
        target=query.target,
        normalized_target=None,
        summary="derived target is unavailable",
        answers=(answer,),
    )


def _compose_derived_qualification(result: QueryResult, source: QueryResult) -> QueryResult:
    """Carry source qualifications into every correlated dependent answer."""
    source_answer = source.answers[0]
    composed: list[QueryAnswer] = []
    for answer in result.answers:
        conditions = tuple(dict.fromkeys((*answer.conditions, *source_answer.conditions)))
        uses = tuple(
            {
                (item.name, item.relationship): item
                for item in (*answer.assumptions_used, *source_answer.assumptions_used)
            }.values()
        )
        unsupported = tuple(
            dict.fromkeys(
                (
                    *answer.relevant_unsupported_assumptions,
                    *source_answer.relevant_unsupported_assumptions,
                )
            )
        )
        constraint_uses = tuple(
            {
                item.model_dump_json(): item
                for item in (*answer.constraint_uses, *source_answer.constraint_uses)
            }.values()
        )
        if (
            len(conditions) > 256
            or len(uses) > 128
            or len(unsupported) > 128
            or len(constraint_uses) > 128
        ):
            composed.append(
                answer.model_copy(
                    update={
                        "conclusion": "unresolved",
                        "blockers": tuple(
                            dict.fromkeys(
                                (
                                    *answer.blockers,
                                    "derived target qualification exceeds its bound",
                                )
                            )
                        ),
                    }
                )
            )
            continue
        composed.append(
            answer.model_copy(
                update={
                    "conclusion": "proved_under_assumptions"
                    if answer.conclusion == "proved" and (conditions or uses or constraint_uses)
                    else answer.conclusion,
                    "conditions": conditions,
                    "assumptions_used": uses,
                    "relevant_unsupported_assumptions": unsupported,
                    "constraint_uses": constraint_uses,
                }
            )
        )
    return result.model_copy(update={"answers": tuple(composed)})


def _bound_result(outcome: AnalysisOutcome) -> AnalysisOutcome:
    if isinstance(outcome, AnalysisSuccess):
        advice = outcome.optimization
        # Preserve the pre-advice success population exactly: the optional
        # internal field itself must not consume the historical base allowance.
        base_bytes = len(
            outcome.model_dump_json(exclude={"optimization"}).encode("utf-8")
        )
        if base_bytes > MAX_RESULT_BYTES:
            return _complexity_failure("analysis result exceeds its base size bound")
        advice_contribution = (
            len(outcome.model_dump_json().encode("utf-8")) - base_bytes
        )
        if advice_contribution > MAX_OPTIMIZATION_BYTES:
            qualification = (
                "optimization advice bytes budget exhausted "
                f"(measured {advice_contribution}, configured {MAX_OPTIMIZATION_BYTES})"
            )
            for retained in range(len(advice.plans), -1, -1):
                bounded_advice = advice.model_copy(
                    update={
                        "suggestions": advice.suggestions[:retained],
                        "plans": advice.plans[:retained],
                        "projection_status": "truncated",
                        "projection_qualifications": tuple(
                            dict.fromkeys((*advice.projection_qualifications, qualification))
                        ),
                    }
                )
                bounded_outcome = outcome.model_copy(
                    update={"optimization": bounded_advice}
                )
                bounded_contribution = (
                    len(bounded_outcome.model_dump_json().encode("utf-8")) - base_bytes
                )
                if bounded_contribution <= MAX_OPTIMIZATION_BYTES:
                    outcome = bounded_outcome
                    break
            else:
                # A pathological pre-existing qualification can consume the entire
                # optimization allowance. Preserve the valid base analysis and both
                # diagnostic classes with bounded summaries rather than promoting a
                # passive presentation limit to a whole-analysis failure.
                search_qualifications = advice.qualifications
                if advice.status == "incomplete":
                    search_qualifications = (
                        "optimization search qualifications truncated by output projection",
                    )
                bounded_advice = advice.model_copy(
                    update={
                        "suggestions": (),
                        "plans": (),
                        "qualifications": search_qualifications,
                        "projection_status": "truncated",
                        "projection_qualifications": (
                            "optimization advice bytes budget exhausted",
                        ),
                    }
                )
                outcome = outcome.model_copy(update={"optimization": bounded_advice})
        if len(outcome.model_dump_json().encode("utf-8")) > MAX_COMBINED_RESULT_BYTES:
            return _complexity_failure("analysis result exceeds its combined size bound")
    return outcome
