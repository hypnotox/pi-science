# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Service-owned query attachment and derived-target correlation."""

from __future__ import annotations

from py_science.formula._analysis.computation import _invalid
from py_science.formula._analysis.retained import Knowledge, NamedRelationship, RetainedComputation
from py_science.formula.expressions import (
    Equation,
    ExpressionTooComplex,
    Relationship,
    RelationshipOperator,
    Symbol,
)
from py_science.formula.models import (
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisRequest,
    AsymptoticQuery,
    AsymptoticResult,
    ClosedFormEvidence,
    ClosedFormResult,
    ConstraintUse,
    DerivedTarget,
    EquationReport,
    EquationRequest,
    EquationTarget,
    EquivalenceQuery,
    EquivalenceResult,
    ExpressionTarget,
    LimitQuery,
    LimitResult,
    MathematicalDomain,
    PropertiesQuery,
    PropertiesResult,
    QueryAnswer,
    QueryResult,
    SourceReference,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.query import QueryTarget, evaluate_queries
from py_science.formula.reasoning import ReasoningContext


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
        evaluated = evaluate_queries((query,), target, query_reasoning, query_reserved_names)
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
