# ruff: noqa: E501
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from itertools import product
from math import ceil, floor
from types import MappingProxyType

from py_science.formula.analyzer import OperationTally, count_operations
from py_science.formula.computation import (
    Knowledge,
    NamedDefinition,
    NamedRelationship,
    ParsedEquation,
    Producer,
    RetainedComputation,
    RetainedWorkAnalysis,
)
from py_science.formula.domains import OutputDomain, build_output_domains
from py_science.formula.domains import extent as domain_extent
from py_science.formula.exact_values import parse_exact_scalar
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    Let,
    RationalLiteral,
    Relationship,
    RelationshipOperator,
    Sum,
    Symbol,
    exact_integer_value,
    expression_children,
    expression_node_count,
    lower_let_bindings,
    substitute,
)
from py_science.formula.models import (
    AnalysisError,
    AnalysisErrorCode,
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
    DomainConstraint,
    DominanceAnalysisOutcome,
    DominanceAnalysisRequest,
    EffectiveIndexDomain,
    EquationEffectiveDomains,
    EquationReport,
    EquationRequest,
    EquationTarget,
    EquivalenceQuery,
    EquivalenceResult,
    ExpressionTarget,
    Interpretation,
    IntervalBound,
    IntervalResult,
    LimitQuery,
    LimitResult,
    MathematicalDomain,
    OperationCounts,
    OptimizationFailure,
    OptimizationReport,
    OptimizationSuccess,
    OptimizeOutcome,
    OptimizeRequest,
    PropertiesQuery,
    PropertiesResult,
    QueryAnswer,
    QueryResult,
    RelationshipUse,
    ReuseReport,
    Scenario,
    ScenarioResult,
    SourceLocation,
    SourceReference,
    SourceSpan,
    SystemReport,
    VariablePropertyCheck,
)
from py_science.formula.optimization import (
    _extraction_opportunities,  # pyright: ignore[reportPrivateUsage]
    _optimization_report,  # pyright: ignore[reportPrivateUsage]
)
from py_science.formula.parser import ParseFailure, ParseFailureKind, parse_expression
from py_science.formula.query import QueryTarget, evaluate_queries
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import (
    NormalizationError,
    NormalizedRendering,
    is_nondecreasing_polynomial,
    polynomial_degree,
    render,
    render_system,
)
from py_science.formula.work import (
    MAX_WORK_NODES,
    FunctionRule,
    PrimitiveRule,
    WorkAnalysis,
    WorkContext,
    WorkRenderBudget,
    aggregate_output_analysis,
    analyze_work,
    expand_function_values,
    is_integer_expression,
    is_nonnegative_expression,
    is_positive_expression,
    map_analysis,
    render_invocations,
    render_operations,
    render_work,
    replace_exact,
    simplify_constants,
    substitute_analysis,
)

MAX_REQUEST_BYTES = 262_144
MAX_REQUEST_NODES = 16_384
MAX_RESULT_BYTES = 262_144
MAX_OPTIMIZATION_BYTES = 262_144
MAX_COMBINED_RESULT_BYTES = MAX_RESULT_BYTES + MAX_OPTIMIZATION_BYTES
MAX_RENDERED_BYTES = 196_608


def _retain_work_analysis(analysis: WorkAnalysis) -> RetainedWorkAnalysis:
    return RetainedWorkAnalysis(
        operations=analysis.operations,
        opaque_work=analysis.opaque_work,
        invocations=MappingProxyType(dict(analysis.invocations)),
        unknown_costs=frozenset(analysis.unknown_costs),
        unresolved=frozenset(analysis.unresolved),
        direct_work_blockers=frozenset(analysis.direct_work_blockers),
    )


class FormulaLoader:
    def __init__(self) -> None:
        self.nodes = 0

    def parse(
        self, source: str, path: str
    ) -> Expression | Equation | Relationship | AnalysisFailure:
        parsed = parse_expression(source)
        if isinstance(parsed, ParseFailure):
            return _parse_failure(parsed, path, source)
        formula_nodes = (
            expression_node_count(parsed.left) + expression_node_count(parsed.right) + 1
            if isinstance(parsed, (Equation, Relationship))
            else expression_node_count(parsed)
        )
        self.nodes += formula_nodes
        if self.nodes > MAX_REQUEST_NODES:
            return _complexity_failure("request mathematical structure is too complex")
        return parsed


class RenderingBudget:
    def __init__(self) -> None:
        self.bytes = 0

    def accept(self, rendering: NormalizedRendering) -> Interpretation | AnalysisFailure:
        self.bytes += len(rendering.sympy.encode("utf-8"))
        self.bytes += len(rendering.latex.encode("utf-8"))
        if self.bytes > MAX_RENDERED_BYTES:
            return _complexity_failure("normalized interpretation exceeds its size bound")
        return Interpretation(
            normalized_sympy=rendering.sympy,
            normalized_latex=rendering.latex,
        )


def analyze(request: AnalysisRequest) -> AnalysisOutcome:
    """Analyze one ordinary request; comparison uses the retained private bundle."""
    result = _analyze_computation(request)
    if isinstance(result, AnalysisFailure):
        return _bound_result(result)
    outcome: AnalysisOutcome = result.success
    if request.queries:
        outcome = _attach_queries(request, result)
    if isinstance(outcome, AnalysisSuccess):
        try:
            optimization = _optimization_report(request, result, result.work_context)
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
            "optimization": {"max_suggestions": request.max_plans, "objective": request.objective},
        })
        computed = _analyze_computation(ordinary)
        if isinstance(computed, AnalysisFailure):
            return OptimizationFailure(error=computed.error.message)
        report = _optimization_report(ordinary, computed, computed.work_context)
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
    from py_science.formula.dominance import analyze_retained

    computed = _analyze_computation(request.analysis_request())
    if isinstance(computed, AnalysisFailure):
        return computed
    fixed_failure = _dominance_fixed_assumption_failure(request, computed)
    if fixed_failure is not None:
        return fixed_failure
    outcome = analyze_retained(request, computed)
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


def _analyze_computation(request: AnalysisRequest) -> RetainedComputation | AnalysisFailure:
    request_failure = _request_size_failure(request)
    if request_failure is not None:
        return request_failure
    loader = FormulaLoader()
    definitions_or_failure = _parse_definitions(request, loader)
    if isinstance(definitions_or_failure, AnalysisFailure):
        return definitions_or_failure
    definitions, primitives = definitions_or_failure
    request_unknown_arities = _unknown_call_arities(definitions, primitives)
    context = WorkContext(
        definitions=definitions,
        primitives=primitives,
        variable_domains={
            name: declaration.domain for name, declaration in request.variables.items()
        },
    )
    knowledge_or_failure = _parse_knowledge(request, loader, context)
    if isinstance(knowledge_or_failure, AnalysisFailure):
        return knowledge_or_failure
    knowledge = knowledge_or_failure
    if request.scenarios:
        try:
            scenario_reasoning = ReasoningContext.build(
                {name: declaration.domain for name, declaration in request.variables.items()},
                knowledge.definitions,
                knowledge.assumptions,
            )
        except ExpressionTooComplex:
            return _complexity_failure("scenario assumptions exceed the reasoning bound")
        scenario_failure = _scenario_domain_failure(request, scenario_reasoning)
        if scenario_failure is not None:
            return scenario_failure
    try:
        if request.expression is not None:
            analyzed = _analyze_single(
                request,
                request.expression,
                loader,
                context,
                request_unknown_arities,
                knowledge,
            )
        else:
            analyzed = _analyze_system(
                request,
                loader,
                context,
                request_unknown_arities,
                knowledge,
            )
    except ExpressionTooComplex as error:
        return _complexity_failure(str(error))
    if isinstance(analyzed, AnalysisFailure):
        return analyzed
    return analyzed


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


def _parse_knowledge(
    request: AnalysisRequest,
    loader: FormulaLoader,
    context: WorkContext,
) -> Knowledge | AnalysisFailure:
    assumptions: list[NamedRelationship] = []
    for position, item in enumerate(request.assumptions):
        parsed = loader.parse(item.relationship, f"assumptions[{position}].relationship")
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if not isinstance(parsed, Relationship):
            return _invalid(
                f"assumption {item.name} must be an equality or inequality",
                source=SourceReference(path=f"assumptions[{position}].relationship"),
            )
        reserved_names = set(request.variables) | {item.variable for item in request.definitions}
        let_error = _validate_let_names(parsed.left, reserved_names) or _validate_let_names(
            parsed.right, reserved_names
        )
        if let_error is not None:
            return _invalid(let_error)
        assumptions.append(NamedRelationship(item.name, item.relationship, parsed))
    parsed_definitions: list[tuple[int, str, str, Expression]] = []
    for position, item in enumerate(request.definitions):
        parsed = loader.parse(item.expression, f"definitions[{position}].expression")
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, (Equation, Relationship)):
            return _invalid(
                f"definition {item.variable} must be an expression",
                source=SourceReference(path=f"definitions[{position}].expression"),
            )
        let_error = _validate_let_names(
            parsed,
            set(request.variables) | {item.variable for item in request.definitions},
        )
        if let_error is not None:
            return _invalid(let_error)
        parsed_definitions.append((position, item.variable, item.expression, parsed))
    graph = {
        name: _symbol_names(expression) & {other[1] for other in parsed_definitions}
        for _, name, _, expression in parsed_definitions
    }
    order = _topological(graph)
    if order is None:
        return _invalid("directed definitions contain a cycle")
    parsed_by_name = {
        name: (position, source, expression)
        for position, name, source, expression in parsed_definitions
    }
    resolved_definitions: dict[str, Expression] = {}
    definitions: list[NamedDefinition] = []
    for name in order:
        position, source, expression = parsed_by_name[name]
        resolved = substitute(expression, resolved_definitions, max_nodes=MAX_WORK_NODES)
        domain_result = _definition_domain_result(
            name,
            resolved,
            request,
            context,
            SourceReference(path=f"definitions[{position}].expression"),
            SourceReference(path=f"definitions[{position}].variable"),
        )
        if isinstance(domain_result, AnalysisFailure):
            return domain_result
        resolved_definitions[name] = resolved
        definitions.append(NamedDefinition(name, f"{name} = {source}", expression, domain_result))
    for scenario_position, scenario in enumerate(request.scenarios):
        scenario_expressions: dict[str, Expression] = {}
        for definition_position, definition in enumerate(scenario.definitions):
            definition_path = (
                f"scenarios[{scenario_position}].definitions[{definition_position}].expression"
            )
            parsed = loader.parse(definition.expression, definition_path)
            if isinstance(parsed, AnalysisFailure):
                return parsed
            if isinstance(parsed, (Equation, Relationship)):
                return _invalid(
                    f"scenario {scenario.name} definition "
                    f"{definition.variable} must be an expression",
                    source=SourceReference(path=definition_path),
                )
            if _contains_infinity(parsed):
                return _invalid(
                    f"scenario {scenario.name} definition {definition.variable} must be finite",
                    source=SourceReference(path=definition_path),
                    supported_alternative="use a finite scenario work definition",
                )
            let_error = _validate_let_names(
                parsed,
                set(request.variables)
                | {item.variable for item in request.definitions}
                | {item.variable for item in scenario.definitions},
            )
            if let_error is not None:
                return _invalid(let_error)
            scenario_expressions[definition.variable] = parsed
        globally_defined = set(resolved_definitions)
        overlapping_treatments = (
            set(scenario.fixed)
            | set(scenario.choices)
            | set(scenario_expressions)
            | set(scenario.asymptotic)
            | set(scenario.bounds)
        ) & globally_defined
        if overlapping_treatments:
            return _invalid(
                f"scenario {scenario.name} treatments conflict with global definitions: "
                + ", ".join(sorted(overlapping_treatments))
            )
        scenario_qualifications = _scenario_definition_qualifications(
            scenario,
            scenario_expressions,
            request,
            context,
            resolved_definitions,
            scenario_position,
        )
        if isinstance(scenario_qualifications, AnalysisFailure):
            return _invalid(
                f"scenario {scenario.name}: {scenario_qualifications.error.message}",
                source=scenario_qualifications.error.source,
            )
    by_name = {item.name: item for item in definitions}
    contradiction = _direct_contradiction(tuple(assumptions), request)
    if contradiction is not None:
        return _invalid(contradiction)
    return Knowledge(tuple(assumptions), tuple(by_name[name] for name in order))


def _scenario_literal(value: str | int) -> Expression:
    exact = parse_exact_scalar(str(value))
    assert exact is not None
    if exact.denominator == 1:
        return IntegerLiteral(exact.numerator)
    return RationalLiteral(exact.numerator, exact.denominator)


def _exact_fraction(value: str | int) -> Fraction:
    exact = parse_exact_scalar(str(value))
    assert exact is not None
    return Fraction(exact.numerator, exact.denominator)


def _constant_value(expression: Expression) -> Fraction | None:
    if isinstance(expression, IntegerLiteral):
        return Fraction(expression.value)
    if isinstance(expression, RationalLiteral):
        return Fraction(expression.numerator, expression.positive_denominator)
    if isinstance(expression, InfinityLiteral):
        return None
    if not isinstance(expression, BinaryExpression):
        return None
    left = _constant_value(expression.left)
    right = _constant_value(expression.right)
    if left is None or right is None:
        return None
    if expression.operator is BinaryOperator.ADD:
        return left + right
    if expression.operator is BinaryOperator.SUBTRACT:
        return left - right
    if expression.operator is BinaryOperator.MULTIPLY:
        return left * right
    if expression.operator is BinaryOperator.DIVIDE:
        return None if right == 0 else left / right
    if expression.operator is BinaryOperator.POWER and right.denominator == 1:
        exponent = right.numerator
        if left == 0 and exponent < 0:
            return None
        magnitude_bits = max(left.numerator.bit_length(), left.denominator.bit_length())
        if abs(exponent) > 4_096 or magnitude_bits * abs(exponent) > 16_384:
            return None
        return left**exponent
    return None


def _is_real_expression(expression: Expression, context: WorkContext) -> bool:
    if isinstance(expression, (IntegerLiteral, RationalLiteral)):
        return True
    if isinstance(expression, InfinityLiteral):
        return False
    if isinstance(expression, (Symbol, IndexedValue)):
        return expression.name in context.variable_domains
    if isinstance(expression, Call):
        return False
    if isinstance(expression, Sum):
        return (
            _is_real_expression(expression.body, context.with_integer_symbol(expression.index))
            and is_integer_expression(expression.lower, context)
            and is_integer_expression(expression.upper, context)
        )
    if isinstance(expression, Let):
        try:
            return _is_real_expression(lower_let_bindings(expression), context)
        except ExpressionTooComplex:
            return False
    if not _is_real_expression(expression.left, context) or not _is_real_expression(
        expression.right, context
    ):
        return False
    if expression.operator in {
        BinaryOperator.ADD,
        BinaryOperator.SUBTRACT,
        BinaryOperator.MULTIPLY,
    }:
        return True
    if expression.operator is BinaryOperator.DIVIDE:
        denominator = _constant_value(expression.right)
        return (denominator is not None and denominator != 0) or is_positive_expression(
            expression.right, context
        )
    exponent = exact_integer_value(expression.right)
    return expression.operator is BinaryOperator.POWER and exponent is not None and exponent >= 0


def _definition_domain_result(
    variable: str,
    expression: Expression,
    request: AnalysisRequest,
    context: WorkContext,
    source: SourceReference | None = None,
    target_source: SourceReference | None = None,
) -> str | AnalysisFailure | None:
    declaration = request.variables.get(variable)
    if declaration is None:
        return _invalid(
            f"definition target {variable} is undeclared",
            source=target_source or source,
        )
    references = _external_value_names(expression, set(), set()) - set(request.variables)
    if references:
        return _invalid(
            f"definition for {variable} references undeclared variables: "
            + ", ".join(sorted(references)),
            source=source,
        )
    value = _constant_value(expression)
    if value is not None:
        contradicts = (
            (declaration.domain.is_integer and value.denominator != 1)
            or (
                declaration.domain
                in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL}
                and value <= 0
            )
            or (
                declaration.domain
                in {MathematicalDomain.NONNEGATIVE_INTEGER, MathematicalDomain.NONNEGATIVE_REAL}
                and value < 0
            )
        )
        if contradicts:
            return _invalid(f"definition contradicts declared domain for {variable}", source=source)
    proven = {
        MathematicalDomain.INTEGER: is_integer_expression(expression, context),
        MathematicalDomain.NONNEGATIVE_INTEGER: is_integer_expression(expression, context)
        and is_nonnegative_expression(expression, context),
        MathematicalDomain.POSITIVE_INTEGER: is_integer_expression(expression, context)
        and is_positive_expression(expression, context),
        MathematicalDomain.REAL: _is_real_expression(expression, context),
        MathematicalDomain.POSITIVE_REAL: is_positive_expression(expression, context),
        MathematicalDomain.NONNEGATIVE_REAL: _is_real_expression(expression, context)
        and is_nonnegative_expression(expression, context),
    }[declaration.domain]
    if proven:
        return None
    return f"definition for {variable}: declared-domain preservation is unproved"


def _scenario_definition_qualifications(
    scenario: Scenario,
    expressions: dict[str, Expression],
    request: AnalysisRequest,
    context: WorkContext,
    base_replacements: dict[str, Expression] | None = None,
    scenario_position: int | None = None,
) -> dict[str, str | None] | AnalysisFailure:
    names = set(expressions)
    graph = {name: _symbol_names(expression) & names for name, expression in expressions.items()}
    order = _topological(graph)
    if order is None:
        return _invalid("definitions contain a cycle")

    for name, value in scenario.fixed.items():
        result = _definition_domain_result(
            name,
            _scenario_literal(value),
            request,
            context,
            SourceReference(path=f"scenarios[{scenario_position}].fixed.{name}"),
        )
        if isinstance(result, AnalysisFailure):
            return result
    for name, values in scenario.choices.items():
        for value in values:
            result = _definition_domain_result(
                name,
                _scenario_literal(value),
                request,
                context,
                SourceReference(path=f"scenarios[{scenario_position}].choices.{name}"),
            )
            if isinstance(result, AnalysisFailure):
                return result

    qualifications: dict[str, str | None] = {name: None for name in expressions}
    choice_names = sorted(scenario.choices)
    choice_values = [scenario.choices[name] for name in choice_names]
    for selected_values in product(*choice_values):
        scenario_values: dict[str, Expression] = {
            name: _scenario_literal(value) for name, value in scenario.fixed.items()
        }
        scenario_values.update(
            {
                name: _scenario_literal(value)
                for name, value in zip(choice_names, selected_values, strict=True)
            }
        )
        replacements = _compose_replacements(base_replacements or {}, scenario_values)
        for name in base_replacements or {}:
            result = _definition_domain_result(name, replacements[name], request, context)
            if isinstance(result, AnalysisFailure):
                return result
        for name in order:
            resolved = substitute(expressions[name], replacements, max_nodes=MAX_WORK_NODES)
            result = _definition_domain_result(name, resolved, request, context)
            if isinstance(result, AnalysisFailure):
                return result
            if result is not None:
                qualifications[name] = result
            replacements[name] = resolved
    return qualifications


def _literal_relationship_truth(relation: Relationship) -> bool | None:
    left = _constant_value(relation.left)
    right = _constant_value(relation.right)
    if left is None or right is None:
        return None
    return {
        RelationshipOperator.EQUAL: left == right,
        RelationshipOperator.LESS: left < right,
        RelationshipOperator.LESS_EQUAL: left <= right,
        RelationshipOperator.GREATER: left > right,
        RelationshipOperator.GREATER_EQUAL: left >= right,
    }[relation.operator]


def _direct_contradiction(
    assumptions: tuple[NamedRelationship, ...], request: AnalysisRequest
) -> str | None:
    bounds: dict[Expression, dict[str, tuple[Fraction, bool]]] = {}
    reverse = {
        RelationshipOperator.LESS: RelationshipOperator.GREATER,
        RelationshipOperator.LESS_EQUAL: RelationshipOperator.GREATER_EQUAL,
        RelationshipOperator.GREATER: RelationshipOperator.LESS,
        RelationshipOperator.GREATER_EQUAL: RelationshipOperator.LESS_EQUAL,
        RelationshipOperator.EQUAL: RelationshipOperator.EQUAL,
    }
    for item in assumptions:
        relation = item.value
        literal_truth = _literal_relationship_truth(relation)
        if literal_truth is False:
            return f"assumption {item.name} is a false literal relationship"
        if literal_truth is True:
            continue
        right_value = _constant_value(relation.right)
        left_value = _constant_value(relation.left)
        if right_value is not None:
            expression, value, operator = relation.left, right_value, relation.operator
        elif left_value is not None:
            expression, value = relation.right, left_value
            operator = reverse[relation.operator]
        else:
            continue
        entry = bounds.setdefault(expression, {})
        candidates: tuple[tuple[str, tuple[Fraction, bool]], ...]
        if operator is RelationshipOperator.EQUAL:
            candidates = (("lower", (value, True)), ("upper", (value, True)))
        elif operator in {RelationshipOperator.GREATER, RelationshipOperator.GREATER_EQUAL}:
            candidates = (("lower", (value, operator is RelationshipOperator.GREATER_EQUAL)),)
        else:
            candidates = (("upper", (value, operator is RelationshipOperator.LESS_EQUAL)),)
        for kind, candidate in candidates:
            prior = entry.get(kind)
            if (
                prior is None
                or (kind == "lower" and candidate[0] > prior[0])
                or (kind == "upper" and candidate[0] < prior[0])
            ):
                entry[kind] = candidate
            elif prior[0] == candidate[0]:
                entry[kind] = (prior[0], prior[1] and candidate[1])
        lower = entry.get("lower")
        upper = entry.get("upper")
        if (
            lower is not None
            and upper is not None
            and (lower[0] > upper[0] or (lower[0] == upper[0] and not (lower[1] and upper[1])))
        ):
            return "contradictory assumptions bound the same expression outside an interval"
        if isinstance(expression, Symbol):
            declaration = request.variables.get(expression.name)
            if (
                declaration is not None
                and declaration.domain.is_integer
                and lower is not None
                and upper is not None
            ):
                least_integer = ceil(lower[0]) if lower[1] else floor(lower[0]) + 1
                greatest_integer = floor(upper[0]) if upper[1] else ceil(upper[0]) - 1
                if least_integer > greatest_integer:
                    return "contradictory assumptions define an empty integer interval"
            if declaration is not None:
                domain_lower = {
                    MathematicalDomain.POSITIVE_INTEGER: (Fraction(1), True),
                    MathematicalDomain.POSITIVE_REAL: (Fraction(0), False),
                    MathematicalDomain.NONNEGATIVE_INTEGER: (Fraction(0), True),
                }.get(declaration.domain)
                if (
                    domain_lower is not None
                    and upper is not None
                    and (
                        upper[0] < domain_lower[0]
                        or (upper[0] == domain_lower[0] and not (upper[1] and domain_lower[1]))
                    )
                ):
                    return f"assumption contradicts declared domain for {expression.name}"
    return None


def _parse_definitions(
    request: AnalysisRequest,
    loader: FormulaLoader,
) -> tuple[dict[str, FunctionRule], dict[str, PrimitiveRule]] | AnalysisFailure:
    definitions: dict[str, FunctionRule] = {}
    primitives: dict[str, PrimitiveRule] = {}
    for position, definition in enumerate(request.functions):
        parsed = loader.parse(definition.body, f"functions[{position}].body")
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, (Equation, Relationship)):
            return _invalid(f"function {definition.name} body cannot contain a relationship")
        let_error = _validate_let_names(parsed, set(definition.parameters))
        if let_error is not None:
            return _invalid(f"function {definition.name}: {let_error}")
        index_error, _ = _validate_index_scopes(
            parsed,
            set(definition.parameters),
            WorkContext({}, {}, {}),
        )
        if index_error is not None:
            return _invalid(f"function {definition.name}: {index_error}")
        unknown = _external_value_names(parsed, set(definition.parameters), set())
        if unknown:
            return _invalid(
                f"function {definition.name} body uses undeclared parameters: "
                + ", ".join(sorted(unknown))
            )
        definitions[definition.name] = FunctionRule(
            definition.name,
            definition.parameters,
            parsed,
            definition.body,
        )
    for position, primitive in enumerate(request.primitive_costs):
        primitive_path = f"primitive_costs[{position}].work"
        parsed = loader.parse(primitive.work, primitive_path)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, (Equation, Relationship)):
            return _invalid(f"primitive cost {primitive.name} cannot contain a relationship")
        if _contains_infinity(parsed):
            return _invalid(
                f"primitive cost {primitive.name} must be finite",
                source=SourceReference(path=primitive_path),
                supported_alternative="use a finite symbolic work expression",
            )
        let_error = _validate_let_names(parsed, set(primitive.parameters))
        if let_error is not None:
            return _invalid(f"primitive cost {primitive.name}: {let_error}")
        index_error, _ = _validate_index_scopes(
            parsed,
            set(primitive.parameters),
            WorkContext({}, {}, {}),
        )
        if index_error is not None:
            return _invalid(f"primitive cost {primitive.name}: {index_error}")
        unknown = _external_value_names(parsed, set(primitive.parameters), set())
        if unknown:
            return _invalid(
                f"primitive cost {primitive.name} uses undeclared parameters: "
                + ", ".join(sorted(unknown))
            )
        primitives[primitive.name] = PrimitiveRule(
            primitive.name,
            primitive.parameters,
            parsed,
        )
    call_failure = _validate_function_calls(definitions, primitives)
    if call_failure is not None:
        return call_failure
    return definitions, primitives


def _validate_function_calls(
    definitions: dict[str, FunctionRule],
    primitives: dict[str, PrimitiveRule],
) -> AnalysisFailure | None:
    known_arities = {
        **{name: len(rule.parameters) for name, rule in definitions.items()},
        **{name: len(rule.parameters) for name, rule in primitives.items()},
    }
    unknown_arities: dict[str, int] = {}
    graph: dict[str, set[str]] = {name: set() for name in definitions}
    for name, definition in definitions.items():
        error = _check_call_arities(definition.body, known_arities, unknown_arities)
        if error is not None:
            return error
        graph[name] = {call.name for call in _calls(definition.body) if call.name in definitions}
    for primitive in primitives.values():
        error = _check_call_arities(primitive.work, known_arities, unknown_arities)
        if error is not None:
            return error
    if _topological(graph) is None:
        return _invalid("function definitions contain a cycle")
    return None


def _analyze_single(
    request: AnalysisRequest,
    source: str,
    loader: FormulaLoader,
    context: WorkContext,
    request_unknown_arities: dict[str, int],
    knowledge: Knowledge,
) -> RetainedComputation | AnalysisFailure:
    parsed = loader.parse(source, "expression")
    if isinstance(parsed, AnalysisFailure):
        return parsed
    if isinstance(parsed, (Equation, Relationship)):
        return _unsupported("relationships are supported only in assumption fields")
    let_error = _validate_let_names(
        parsed,
        set(request.variables) | {item.variable for item in request.definitions},
    )
    if let_error is not None:
        return _invalid(let_error)
    call_failure = _check_call_arities(
        parsed,
        {
            **{name: len(rule.parameters) for name, rule in context.definitions.items()},
            **{name: len(rule.parameters) for name, rule in context.primitives.items()},
        },
        dict(request_unknown_arities),
    )
    if call_failure is not None:
        return call_failure
    try:
        normalized = render(parsed)
    except NormalizationError:
        return _normalization_failure()
    budget = RenderingBudget()
    interpretation = budget.accept(normalized)
    if isinstance(interpretation, AnalysisFailure):
        return interpretation
    tally = count_operations(parsed)
    advanced = bool(
        request.functions
        or request.primitive_costs
        or request.variables
        or request.assumptions
        or request.definitions
        or request.scenarios
        or _contains_advanced(parsed)
    )
    if not advanced:
        success = AnalysisSuccess(
            interpretation=interpretation,
            operation_counts=_counts(tally),
            abstract_work=tally.total,
        )
        analysis = _retain_work_analysis(analyze_work(parsed, context))
        return RetainedComputation(
            success=success,
            expression=parsed,
            equations=(),
            producers=MappingProxyType({}),
            dependency_order=(),
            equation_analyses=MappingProxyType({"expression": analysis}),
            aggregate_analysis=analysis,
            knowledge=knowledge,
            work_context=context,
        )
    index_error, index_unresolved = _validate_index_scopes(parsed, set(), context)
    if index_error is not None:
        return _invalid(index_error)
    _bound_substitution_expansion(parsed, context.definitions)
    analysis = analyze_work(parsed, context)
    analysis.unresolved.update(index_unresolved)
    analysis, relationships = _apply_knowledge(
        analysis, knowledge, context.definitions, mathematical_expression=parsed
    )
    work_render_budget = WorkRenderBudget()
    report = _equation_report(
        "expression",
        interpretation,
        tally,
        analysis,
        (),
        work_render_budget,
        relationships,
    )
    system = _system_report(
        (report,),
        WorkAnalysis().combine(analysis),
        (),
        (),
        (),
        work_render_budget,
        relationships,
        tuple(
            item.name
            for item in knowledge.assumptions
            if item.name not in {used.name for used in relationships}
        ),
    )
    blockers = tuple(sorted(analysis.direct_work_blockers))
    if blockers and request.scenarios:
        return _invalid(
            "scenarios require finite direct-evaluation work",
            source=SourceReference(path="scenarios"),
            supported_alternative="remove scenarios to inspect non-finite mathematical structure",
        )
    success = AnalysisSuccess(
        interpretation=interpretation,
        operation_counts=_counts(tally),
        abstract_work=None if blockers else tally.total,
        direct_work_applicability="not_finite" if blockers else "finite",
        direct_work_blockers=blockers,
        system=system,
        scenarios=_scenario_results(
            request, analysis, work_render_budget, relationships, knowledge
        ),
    )
    retained_analysis = _retain_work_analysis(analysis)
    return RetainedComputation(
        success=success,
        expression=parsed,
        equations=(),
        producers=MappingProxyType({}),
        dependency_order=(),
        equation_analyses=MappingProxyType({"expression": retained_analysis}),
        aggregate_analysis=retained_analysis,
        knowledge=knowledge,
        work_context=context,
    )


def _analyze_system(
    request: AnalysisRequest,
    loader: FormulaLoader,
    context: WorkContext,
    request_unknown_arities: dict[str, int],
    knowledge: Knowledge,
) -> RetainedComputation | AnalysisFailure:
    parsed_or_failure = _parse_equations(request, loader)
    if isinstance(parsed_or_failure, AnalysisFailure):
        return parsed_or_failure
    equations = parsed_or_failure
    producers_or_failure = _build_producers(equations)
    if isinstance(producers_or_failure, AnalysisFailure):
        return producers_or_failure
    producers = producers_or_failure
    validation = _validate_system(request, equations, producers, context, request_unknown_arities)
    if isinstance(validation, AnalysisFailure):
        return validation
    edges, reference_counts, index_unresolved = validation
    order = _topological(edges)
    if order is None:
        return _invalid("equation dependencies contain a cycle")

    by_name = {equation.name: equation for equation in equations}
    render_budget = RenderingBudget()
    work_render_budget = WorkRenderBudget()
    reports: dict[str, EquationReport] = {}
    analyses: dict[str, WorkAnalysis] = {}
    relationship_uses: dict[tuple[str, str], RelationshipUse] = {}
    try:
        domain_reasoning = ReasoningContext.build(
            {name: declaration.domain for name, declaration in request.variables.items()},
            knowledge.definitions,
            knowledge.assumptions,
        )
    except ExpressionTooComplex:
        return _complexity_failure("output-domain assumptions exceed the reasoning bound")
    compatibility_failure = _globally_empty_constraint_domain(equations, domain_reasoning)
    if compatibility_failure is not None:
        return compatibility_failure
    all_extractions: list[str] = []
    for name in order:
        equation = by_name[name]
        try:
            normalized = render(equation.formula)
        except NormalizationError:
            return _normalization_failure()
        interpretation = render_budget.accept(normalized)
        if isinstance(interpretation, AnalysisFailure):
            return interpretation
        scoped_context = WorkContext(
            definitions=context.definitions,
            primitives=context.primitives,
            variable_domains=context.variable_domains,
            integer_symbols=frozenset(equation.domains),
        )
        _bound_substitution_expansion(equation.formula.right, scoped_context.definitions)
        analysis = analyze_work(equation.formula.right, scoped_context)
        analysis.unresolved.update(index_unresolved.get(name, ()))
        analysis, domain_uses = aggregate_output_analysis(
            analysis,
            equation.output_domains,
            equation.domain_order,
            scoped_context,
            domain_reasoning,
            f"equation {name}",
        )
        analysis, used = _apply_knowledge(
            analysis,
            knowledge,
            context.definitions,
            report_unmatched=False,
            mathematical_expression=equation.formula.right,
        )
        used = tuple({item.name: item for item in (*domain_uses, *used)}.values())
        domain_use_names = {item.name for item in domain_uses}
        analysis.unresolved = {
            item
            for item in analysis.unresolved
            if not any(
                item.startswith(f"assumption {used_name}:") for used_name in domain_use_names
            )
        }
        relationship_uses.update({(item.name, item.relationship): item for item in used})
        analyses[name] = analysis
        tally = count_operations(equation.formula.right)
        reports[name] = _equation_report(
            name,
            interpretation,
            tally,
            analysis,
            tuple(sorted(edges[name])),
            work_render_budget,
            used,
            equation.submitted_constraints,
            tuple(
                EffectiveIndexDomain(
                    index=domain.index,
                    lower=render(domain.lower).sympy,
                    upper=render(domain.upper).sympy,
                )
                for domain in equation.output_domains
            ),
        )
        all_extractions.extend(
            _extraction_opportunities(
                name,
                equation.formula.right,
                producers,
                output_indices=equation.domain_order,
                output_domains={
                    domain.index: (domain.lower, domain.upper) for domain in equation.output_domains
                },
            )
        )

    combined = WorkAnalysis()
    for name in order:
        combined = combined.combine(analyses[name])
    assumption_names = {item.name for item in knowledge.assumptions}
    used_assumption_names = {
        item.name for item in relationship_uses.values() if item.name in assumption_names
    }
    for assumption in knowledge.assumptions:
        if (
            assumption.name not in used_assumption_names
            and assumption.value.operator is RelationshipOperator.EQUAL
        ):
            combined.unresolved.add(
                f"assumption {assumption.name}: exact normalized subexpression did not match"
            )
    reuse = tuple(
        ReuseReport(producer=producer, consumer=consumer, references=count)
        for (consumer, producer), count in sorted(reference_counts.items())
    )
    try:
        system_rendering = render_system(tuple(by_name[name].formula for name in order))
    except NormalizationError:
        return _normalization_failure()
    system_interpretation = render_budget.accept(system_rendering)
    if isinstance(system_interpretation, AnalysisFailure):
        return system_interpretation
    used_relationships = tuple(relationship_uses[key] for key in sorted(relationship_uses))
    system = _system_report(
        # Analysis follows dependency order, but report correlation preserves the
        # caller's submitted equation order.
        tuple(reports[equation.name] for equation in equations),
        combined,
        tuple((dependency, name) for name in order for dependency in sorted(edges[name])),
        reuse,
        tuple(sorted(set(all_extractions))),
        work_render_budget,
        used_relationships,
        tuple(
            item.name for item in knowledge.assumptions if item.name not in used_assumption_names
        ),
    )
    submitted = OperationTally()
    for name in order:
        submitted = submitted.combine(count_operations(by_name[name].formula.right))
    blockers = tuple(sorted(combined.direct_work_blockers))
    if blockers and request.scenarios:
        return _invalid(
            "scenarios require finite direct-evaluation work",
            source=SourceReference(path="scenarios"),
            supported_alternative="remove scenarios to inspect non-finite mathematical structure",
        )
    success = AnalysisSuccess(
        interpretation=system_interpretation,
        operation_counts=_counts(submitted),
        abstract_work=None if blockers else submitted.total,
        direct_work_applicability="not_finite" if blockers else "finite",
        direct_work_blockers=tuple(
            f"equation {report.name}: {blocker}"
            for report in system.equations
            if report.direct_work_blockers
            for blocker in report.direct_work_blockers
        )
        if blockers
        else (),
        system=system,
        scenarios=_scenario_results(
            request,
            combined,
            work_render_budget,
            used_relationships,
            knowledge,
            equations,
        ),
    )
    retained_analyses = {
        name: _retain_work_analysis(analysis) for name, analysis in analyses.items()
    }
    return RetainedComputation(
        success=success,
        expression=None,
        equations=equations,
        producers=MappingProxyType(dict(producers)),
        dependency_order=tuple(order),
        equation_analyses=MappingProxyType(retained_analyses),
        aggregate_analysis=_retain_work_analysis(combined),
        knowledge=knowledge,
        work_context=context,
    )


def _parse_equations(
    request: AnalysisRequest,
    loader: FormulaLoader,
) -> tuple[ParsedEquation, ...] | AnalysisFailure:
    result: list[ParsedEquation] = []
    for equation_position, item in enumerate(request.equations):
        parsed = loader.parse(item.expression, f"equations[{equation_position}].expression")
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if not isinstance(parsed, Equation):
            return _invalid(f"equation {item.name} must use Eq(lhs, rhs)")
        lhs_indices_or_failure = _lhs_indices(parsed)
        if isinstance(lhs_indices_or_failure, AnalysisFailure):
            return lhs_indices_or_failure
        if set(item.domains) != set(lhs_indices_or_failure):
            return _invalid(f"equation {item.name} domains must exactly bind its output indices")
        shadowed = set(lhs_indices_or_failure) & set(request.variables)
        if shadowed:
            return _invalid(
                "output index cannot shadow a declared global variable: "
                + ", ".join(sorted(shadowed)),
                source=SourceReference(path=f"equations[{equation_position}].expression"),
            )
        domains: dict[str, tuple[Expression, Expression]] = {}
        for index, domain in item.domains.items():
            lower_path = f"equations[{equation_position}].domains.{index}.lower"
            upper_path = f"equations[{equation_position}].domains.{index}.upper"
            lower = loader.parse(domain.lower, lower_path)
            if isinstance(lower, AnalysisFailure):
                return lower
            upper = loader.parse(domain.upper, upper_path)
            if isinstance(upper, AnalysisFailure):
                return upper
            if isinstance(lower, (Equation, Relationship)) or isinstance(
                upper, (Equation, Relationship)
            ):
                return _invalid(f"equation {item.name} domain bounds cannot contain Eq")
            if _contains_infinity(lower):
                return _invalid(
                    f"equation {item.name} domain bounds cannot be infinite",
                    source=SourceReference(path=lower_path),
                    supported_alternative="use a finite computational domain bound",
                )
            if _contains_infinity(upper):
                return _invalid(
                    f"equation {item.name} domain bounds cannot be infinite",
                    source=SourceReference(path=upper_path),
                    supported_alternative="use a finite computational domain bound",
                )
            domains[index] = (lower, upper)
        constraints: list[tuple[str, str, Relationship]] = []
        for constraint_position, constraint in enumerate(item.constraints):
            path = f"equations[{equation_position}].constraints[{constraint_position}].relationship"
            relationship = loader.parse(constraint.relationship, path)
            if isinstance(relationship, AnalysisFailure):
                return relationship
            if not isinstance(relationship, Relationship):
                return _invalid(
                    "domain constraint must be a relationship",
                    source=SourceReference(path=path),
                )
            if constraint.target not in lhs_indices_or_failure:
                return _invalid(
                    f"constraint target {constraint.target} is not an output index",
                    source=SourceReference(
                        path=f"equations[{equation_position}].constraints[{constraint_position}].target"
                    ),
                )
            constraints.append((str(constraint_position), constraint.target, relationship))
        built = build_output_domains(
            domains,
            lhs_indices_or_failure,
            equation_position,
            frozenset(
                name
                for name, declaration in request.variables.items()
                if declaration.domain.is_integer
            ),
            tuple(constraints),
        )
        if not isinstance(built, tuple):
            return _invalid(
                f"equation {item.name}: {built.message}",
                source=SourceReference(path=built.path),
            )
        output_domains, domain_order = built
        result.append(
            ParsedEquation(
                item.name,
                item.constraints,
                parsed,
                MappingProxyType(dict(domains)),
                tuple(constraints),
                output_domains,
                domain_order,
            )
        )
    return tuple(result)


def _globally_empty_constraint_domain(
    equations: tuple[ParsedEquation, ...], reasoning: ReasoningContext
) -> AnalysisFailure | None:
    """Reject only a bounded proof that a local intersection is uniformly empty.

    Reversing an inclusive extent proves `lower > upper` under global facts and
    predecessor extrema.  Failure to prove it deliberately leaves a symbolic
    intersection qualified rather than turning uncertainty into refusal.
    """
    for equation_position, equation in enumerate(equations):
        predecessors = {domain.index: domain for domain in equation.output_domains}
        for domain in equation.output_domains:
            if not any(target == domain.index for _, target, _ in equation.constraints):
                continue
            # An inclusive integer interval is empty only when lower > upper.
            # `extent` proves nonnegativity, so reverse an extent shifted by two:
            # lower - (upper + 2) + 1 == lower - upper - 1.
            reverse = OutputDomain(
                domain.index,
                BinaryExpression(BinaryOperator.ADD, domain.upper, IntegerLiteral(2)),
                domain.lower,
                domain.upper_path,
                domain.lower_path,
                domain.dependencies,
            )
            _, empty, _ = domain_extent(reverse, predecessors, reasoning)
            if not empty:
                continue
            constraint_position = next(
                position
                for position, (_, target, _) in enumerate(equation.constraints)
                if target == domain.index
            )
            return _invalid(
                f"equation {equation.name}: local constraint intersection is uniformly empty under global facts",
                source=SourceReference(
                    path=f"equations[{equation_position}].constraints[{constraint_position}].relationship"
                ),
            )
    return None


def _build_producers(
    equations: tuple[ParsedEquation, ...],
) -> dict[str, Producer] | AnalysisFailure:
    producers: dict[str, Producer] = {}
    for equation in equations:
        value_name = equation.formula.left.name
        arity = (
            len(equation.formula.left.indices)
            if isinstance(equation.formula.left, IndexedValue)
            else 0
        )
        if value_name in producers:
            return _invalid(f"result {value_name} has more than one producer")
        producers[value_name] = Producer(equation.name, value_name, arity)
    return producers


def _validate_system(
    request: AnalysisRequest,
    equations: tuple[ParsedEquation, ...],
    producers: dict[str, Producer],
    context: WorkContext,
    request_unknown_arities: dict[str, int],
) -> (
    tuple[
        dict[str, set[str]],
        dict[tuple[str, str], int],
        dict[str, tuple[str, ...]],
    ]
    | AnalysisFailure
):
    edges: dict[str, set[str]] = {equation.name: set() for equation in equations}
    references: dict[tuple[str, str], int] = defaultdict(int)
    unresolved: dict[str, tuple[str, ...]] = {}
    known_arities = {
        **{name: len(rule.parameters) for name, rule in context.definitions.items()},
        **{name: len(rule.parameters) for name, rule in context.primitives.items()},
    }
    unknown_arities = dict(request_unknown_arities)
    external: set[str] = set()
    producer_names = set(producers)
    for equation_position, equation in enumerate(equations):
        name = equation.name
        scope = set(equation.domains)
        let_error = _validate_let_names(
            equation.formula.right,
            set(request.variables)
            | {item.variable for item in request.definitions}
            | producer_names
            | scope,
        )
        if let_error is not None:
            return _invalid(f"equation {name}: {let_error}")
        index_error, index_unknown = _validate_index_scopes(
            equation.formula.right,
            scope,
            context,
        )
        if index_error is not None:
            return _invalid(f"equation {name}: {index_error}")
        for index, (lower, upper) in equation.domains.items():
            for endpoint, bound in (("lower", lower), ("upper", upper)):
                bound_path = f"equations[{equation_position}].domains.{index}.{endpoint}"
                referenced_producers = _referenced_producers(bound, producers)
                if referenced_producers:
                    return _invalid(
                        f"equation {name} output-domain bounds cannot reference named results: "
                        + ", ".join(sorted(referenced_producers))
                    )
                call_failure = _check_call_arities(bound, known_arities, unknown_arities)
                if call_failure is not None:
                    return call_failure
                let_error = _validate_let_names(
                    bound,
                    set(request.variables)
                    | {item.variable for item in request.definitions}
                    | producer_names
                    | scope,
                )
                if let_error is not None:
                    return _invalid(f"equation {name} domain: {let_error}")
                bound_error, bound_unknown = _validate_index_scopes(bound, scope, context)
                if bound_error is not None:
                    return _invalid(
                        f"equation {name} domain: {bound_error}",
                        source=SourceReference(path=bound_path),
                    )
                missing_bound = _external_value_names(bound, scope, producer_names) - set(
                    request.variables
                )
                if missing_bound:
                    return _invalid(
                        "system variables require mathematical domains: "
                        + ", ".join(sorted(missing_bound)),
                        source=SourceReference(path=bound_path),
                    )
                index_unknown.update(bound_unknown)
        unresolved[name] = tuple(sorted(index_unknown))
        call_failure = _check_call_arities(
            equation.formula.right,
            known_arities,
            unknown_arities,
        )
        if call_failure is not None:
            return call_failure
        reference_failure = _resolve_references(
            equation.formula.right,
            name,
            producers,
            edges,
            references,
        )
        if reference_failure is not None:
            return reference_failure
        external.update(_external_value_names(equation.formula.right, scope, producer_names))
        for lower, upper in equation.domains.values():
            external.update(_external_value_names(lower, scope, producer_names))
            external.update(_external_value_names(upper, scope, producer_names))
    missing = external - set(request.variables)
    if missing:
        return _invalid(
            "system variables require mathematical domains: " + ", ".join(sorted(missing))
        )
    for consumer, dependencies in edges.items():
        if consumer in dependencies:
            return _invalid(f"equation {consumer} references itself")
    return edges, references, unresolved


def _referenced_producers(
    expression: Expression,
    producers: dict[str, Producer],
) -> set[str]:
    referenced: set[str] = set()
    if isinstance(expression, (Symbol, IndexedValue)) and expression.name in producers:
        referenced.add(expression.name)
    for child in expression_children(expression):
        referenced.update(_referenced_producers(child, producers))
    return referenced


def _resolve_references(
    expression: Expression,
    consumer: str,
    producers: dict[str, Producer],
    edges: dict[str, set[str]],
    references: dict[tuple[str, str], int],
) -> AnalysisFailure | None:
    if isinstance(expression, Symbol) and expression.name in producers:
        producer = producers[expression.name]
        if producer.arity != 0:
            return _invalid(f"result {expression.name} requires {producer.arity} indices")
        edges[consumer].add(producer.equation_name)
        references[(consumer, producer.equation_name)] += 1
    elif isinstance(expression, IndexedValue):
        producer = producers.get(expression.name)
        if producer is not None:
            if producer.arity != len(expression.indices):
                return _invalid(f"result {expression.name} requires {producer.arity} indices")
            edges[consumer].add(producer.equation_name)
            references[(consumer, producer.equation_name)] += 1
    for child in expression_children(expression):
        failure = _resolve_references(child, consumer, producers, edges, references)
        if failure is not None:
            return failure
    return None


def _validate_let_names(expression: Expression, reserved: set[str]) -> str | None:
    if isinstance(expression, Let):
        if expression.name in reserved:
            return f"lexical binding name {expression.name} must be fresh"
        error = _validate_let_names(expression.value, reserved)
        if error is not None:
            return error
        return _validate_let_names(expression.body, reserved | {expression.name})
    if isinstance(expression, Sum):
        for bound in (expression.lower, expression.upper):
            error = _validate_let_names(bound, reserved)
            if error is not None:
                return error
        return _validate_let_names(expression.body, reserved | {expression.index})
    for child in expression_children(expression):
        error = _validate_let_names(child, reserved)
        if error is not None:
            return error
    return None


def _validate_index_scopes(
    expression: Expression,
    scope: set[str],
    context: WorkContext,
) -> tuple[str | None, set[str]]:
    # Equation output domains and function parameters are lexical integer names
    # for index qualification; nested sums extend this scope below.
    context = WorkContext(
        definitions=context.definitions,
        primitives=context.primitives,
        variable_domains=context.variable_domains,
        integer_symbols=context.integer_symbols | frozenset(scope),
        nonnegative_symbols=context.nonnegative_symbols,
        call_stack=context.call_stack,
        lexical_values=context.lexical_values,
    )
    unresolved: set[str] = set()
    if isinstance(expression, IndexedValue):
        for index in expression.indices:
            used = _symbol_names(index)
            out_of_scope = used - scope - set(context.lexical_values)
            if out_of_scope:
                return (
                    "index expression uses out-of-scope indices: "
                    + ", ".join(sorted(out_of_scope)),
                    unresolved,
                )
            if not is_integer_expression(index, context):
                unresolved.add(
                    f"index expression for {expression.name} is not known to be integral"
                )
    if isinstance(expression, Let):
        error, nested = _validate_index_scopes(expression.value, scope, context)
        unresolved.update(nested)
        if error is not None:
            return error, unresolved
        error, nested = _validate_index_scopes(
            expression.body,
            scope,
            context.with_lexical_value(expression.name, expression.value),
        )
        unresolved.update(nested)
        return error, unresolved
    if isinstance(expression, Sum):
        if expression.index in scope:
            return f"sum index {expression.index} shadows an existing index", unresolved
        for bound in (expression.lower, expression.upper):
            error, nested = _validate_index_scopes(bound, scope, context)
            unresolved.update(nested)
            if error is not None:
                return error, unresolved
        error, nested = _validate_index_scopes(
            expression.body,
            scope | {expression.index},
            context.with_integer_symbol(expression.index),
        )
        unresolved.update(nested)
        return error, unresolved
    for child in expression_children(expression):
        error, nested = _validate_index_scopes(child, scope, context)
        unresolved.update(nested)
        if error is not None:
            return error, unresolved
    return None, unresolved


def _lhs_indices(equation: Equation) -> tuple[str, ...] | AnalysisFailure:
    if not isinstance(equation.left, IndexedValue):
        return ()
    names: list[str] = []
    for index in equation.left.indices:
        if not isinstance(index, Symbol):
            return _invalid("equation output indices must be plain named indices")
        names.append(index.name)
    if len(set(names)) != len(names):
        return _invalid("equation output indices must be unique")
    return tuple(names)


def _external_value_names(
    expression: Expression,
    scope: set[str],
    producer_names: set[str],
) -> set[str]:
    if isinstance(expression, Symbol):
        if expression.name in scope or expression.name in producer_names:
            return set()
        return {expression.name}
    if isinstance(expression, IndexedValue):
        external = set() if expression.name in producer_names else {expression.name}
        for index in expression.indices:
            external.update(_external_value_names(index, scope, producer_names))
        return external
    if isinstance(expression, Call):
        external: set[str] = set()
        for argument in expression.arguments:
            external.update(_external_value_names(argument, scope, producer_names))
        return external
    if isinstance(expression, Let):
        external = _external_value_names(expression.value, scope, producer_names)
        external.update(_external_value_names(expression.body, scope | {expression.name}, producer_names))
        return external
    if isinstance(expression, Sum):
        external = _external_value_names(expression.lower, scope, producer_names)
        external.update(_external_value_names(expression.upper, scope, producer_names))
        external.update(
            _external_value_names(
                expression.body,
                scope | {expression.index},
                producer_names,
            )
        )
        return external
    external: set[str] = set()
    for child in expression_children(expression):
        external.update(_external_value_names(child, scope, producer_names))
    return external


def _bound_substitution_expansion(
    expression: Expression,
    definitions: dict[str, FunctionRule],
) -> None:
    """Reject definition inlining before it can create a large derived tree."""

    remaining = MAX_WORK_NODES
    max_depth = 256

    def consume(value: Expression, depth: int) -> None:
        nonlocal remaining
        if depth > max_depth:
            raise ExpressionTooComplex("substitution-expanded work exceeds its depth bound")
        if isinstance(value, Call) and (definition := definitions.get(value.name)) is not None:
            expanded = substitute(
                definition.body,
                dict(zip(definition.parameters, value.arguments, strict=True)),
                max_nodes=MAX_WORK_NODES,
            )
            consume(expanded, depth)
            return
        remaining -= 1
        if remaining < 0:
            raise ExpressionTooComplex("substitution-expanded work exceeds its structural bound")
        for child in expression_children(value):
            consume(child, depth + 1)

    consume(expression, 1)


def _unknown_call_arities(
    definitions: dict[str, FunctionRule], primitives: dict[str, PrimitiveRule]
) -> dict[str, int]:
    known = set(definitions) | set(primitives)
    arities: dict[str, int] = {}
    for rule in (*definitions.values(), *primitives.values()):
        for call in _calls(rule.body if isinstance(rule, FunctionRule) else rule.work):
            if call.name not in known:
                arities.setdefault(call.name, len(call.arguments))
    return arities


def _check_call_arities(
    expression: Expression,
    known_arities: dict[str, int],
    unknown_arities: dict[str, int],
) -> AnalysisFailure | None:
    for call in _calls(expression):
        arity = len(call.arguments)
        expected = known_arities.get(call.name)
        if expected is None:
            expected = unknown_arities.setdefault(call.name, arity)
        if expected != arity:
            return _invalid(f"function {call.name} requires {expected} arguments")
    return None


def _calls(expression: Expression) -> tuple[Call, ...]:
    calls: list[Call] = []
    if isinstance(expression, Call):
        calls.append(expression)
    for child in expression_children(expression):
        calls.extend(_calls(child))
    return tuple(calls)


def _symbol_names(expression: Expression) -> set[str]:
    def collect(value: Expression, bound: frozenset[str]) -> set[str]:
        if isinstance(value, Symbol):
            return set() if value.name in bound else {value.name}
        if isinstance(value, Let):
            return collect(value.value, bound) | collect(value.body, bound | {value.name})
        if isinstance(value, Sum):
            return (
                collect(value.lower, bound)
                | collect(value.upper, bound)
                | collect(value.body, bound | {value.index})
            )
        result: set[str] = set()
        for child in expression_children(value):
            result.update(collect(child, bound))
        return result

    return collect(expression, frozenset())


def _value_names(expression: Expression) -> set[str]:
    result: set[str] = (
        {expression.name} if isinstance(expression, (Symbol, IndexedValue)) else set()
    )
    for child in expression_children(expression):
        result.update(_value_names(child))
    return result


def _indexed_value_names(expression: Expression) -> set[str]:
    result: set[str] = {expression.name} if isinstance(expression, IndexedValue) else set()
    for child in expression_children(expression):
        result.update(_indexed_value_names(child))
    return result


def _contains_infinity(expression: Expression) -> bool:
    return isinstance(expression, InfinityLiteral) or any(
        _contains_infinity(child) for child in expression_children(expression)
    )


def _contains_advanced(expression: Expression) -> bool:
    if isinstance(expression, (IndexedValue, Call, Sum, Let, InfinityLiteral)):
        return True
    return any(_contains_advanced(child) for child in expression_children(expression))


def _canonical_equality_replacement(
    relation: Relationship,
) -> tuple[Expression, Expression] | None:
    left, right = relation.left, relation.right
    if left == right:
        return None
    left_integer = exact_integer_value(left)
    right_integer = exact_integer_value(right)
    if left_integer is not None:
        return (right, IntegerLiteral(left_integer)) if right_integer is None else None
    if right_integer is not None:
        return left, IntegerLiteral(right_integer)
    left_nodes = expression_node_count(left)
    right_nodes = expression_node_count(right)
    if left_nodes > right_nodes:
        return left, right
    if right_nodes > left_nodes:
        return right, left
    return None


def _apply_knowledge(
    analysis: WorkAnalysis,
    knowledge: Knowledge,
    function_definitions: dict[str, FunctionRule],
    *,
    report_unmatched: bool = True,
    mathematical_expression: Expression | None = None,
) -> tuple[WorkAnalysis, tuple[RelationshipUse, ...]]:
    result = analysis
    uses: list[RelationshipUse] = []
    replacements: dict[str, Expression] = {}
    definition_provenance: dict[str, set[str]] = {}
    mathematical_expression_had_infinity = (
        mathematical_expression is not None and _contains_infinity(mathematical_expression)
    )
    used_definitions: set[str] = set()
    for definition in knowledge.definitions:
        dependencies = _symbol_names(definition.expression) & set(replacements)
        expression = substitute(definition.expression, replacements, max_nodes=MAX_WORK_NODES)
        replacements[definition.name] = expression
        definition_provenance[definition.name] = {definition.name}.union(
            *(definition_provenance[name] for name in dependencies)
        )
        updated = substitute_analysis(result, {definition.name: expression})
        definition_changed_expression = False
        if mathematical_expression is not None:
            resolved_mathematical_expression = substitute(
                mathematical_expression,
                {definition.name: expression},
                max_nodes=MAX_WORK_NODES,
            )
            definition_changed_expression = (
                resolved_mathematical_expression != mathematical_expression
            )
            mathematical_expression = resolved_mathematical_expression
        if updated != result or definition_changed_expression:
            used_definitions.update(definition_provenance[definition.name])
            for used_name in definition_provenance[definition.name]:
                qualification = next(
                    item.domain_qualification
                    for item in knowledge.definitions
                    if item.name == used_name
                )
                if qualification is not None:
                    updated.unresolved.add(qualification)
        result = updated
    if (
        mathematical_expression is not None
        and not mathematical_expression_had_infinity
        and _contains_infinity(mathematical_expression)
    ):
        result.direct_work_blockers.add(
            "mathematical infinity has no finite direct-evaluation work"
        )
    for definition in knowledge.definitions:
        if definition.name in used_definitions:
            uses.append(
                RelationshipUse(
                    name=f"definition:{definition.name}", relationship=definition.source
                )
            )
    for assumption in knowledge.assumptions:
        relation = assumption.value
        if _literal_relationship_truth(relation) is True:
            continue
        if relation.operator is not RelationshipOperator.EQUAL:
            result.unresolved.add(
                f"assumption {assumption.name}: inequality inference is unsupported"
            )
            continue
        canonical = _canonical_equality_replacement(relation)
        if canonical is None:
            if relation.left != relation.right:
                result.unresolved.add(
                    f"assumption {assumption.name}: ambiguous equality has no safe "
                    "canonical replacement"
                )
            continue
        target, replacement = canonical
        changed = False

        def transform(
            value: Expression,
            target: Expression = target,
            replacement: Expression = replacement,
        ) -> Expression:
            nonlocal changed
            updated, local = replace_exact(value, target, replacement)
            changed = changed or local
            return updated

        result = map_analysis(result, transform)
        if changed:
            uses.append(RelationshipUse(name=assumption.name, relationship=assumption.source))
        elif report_unmatched:
            result.unresolved.add(
                f"assumption {assumption.name}: exact normalized subexpression did not match"
            )
    used_functions: set[str] = set()

    def expand(value: Expression) -> Expression:
        pending = [call.name for call in _calls(value)]
        while pending:
            name = pending.pop()
            if name in used_functions or name not in function_definitions:
                continue
            used_functions.add(name)
            pending.extend(call.name for call in _calls(function_definitions[name].body))
        return expand_function_values(value, function_definitions)

    result = map_analysis(result, expand)
    for name, definition in function_definitions.items():
        if name in used_functions:
            parameters = ", ".join(definition.parameters)
            uses.append(
                RelationshipUse(
                    name=f"function:{name}",
                    relationship=f"{name}({parameters}) = {definition.source}",
                )
            )
    return result, tuple(uses)


def _resolved_knowledge_definitions(knowledge: Knowledge) -> dict[str, Expression]:
    replacements: dict[str, Expression] = {}
    for definition in knowledge.definitions:
        replacements[definition.name] = substitute(
            definition.expression, replacements, max_nodes=MAX_WORK_NODES
        )
    return replacements


def _compose_replacements(
    base: dict[str, Expression],
    overrides: dict[str, Expression],
) -> dict[str, Expression]:
    composed = dict(overrides)
    for name, expression in base.items():
        composed[name] = substitute(expression, composed, max_nodes=MAX_WORK_NODES)
    return composed


def _scenario_results(
    request: AnalysisRequest,
    general: WorkAnalysis,
    budget: WorkRenderBudget,
    general_relationships: tuple[RelationshipUse, ...],
    knowledge: Knowledge,
    equations: tuple[ParsedEquation, ...] = (),
) -> tuple[ScenarioResult, ...]:
    results: list[ScenarioResult] = []
    global_replacements = _resolved_knowledge_definitions(knowledge)
    declared = set(request.variables)
    indexed_values = _indexed_value_names(general.total_work)
    for scenario in request.scenarios:
        treated = (
            set(scenario.fixed)
            | set(scenario.choices)
            | {item.variable for item in scenario.definitions}
            | set(scenario.asymptotic)
            | set(scenario.bounds)
        )
        unresolved: set[str] = set(general.unresolved)
        qualifications = ["exact general symbolic work preserved"]
        indexed_treatments = (
            set(scenario.fixed)
            | set(scenario.choices)
            | {item.variable for item in scenario.definitions}
        ) & indexed_values
        if indexed_treatments:
            unresolved.add(
                "scalar substitution is unsupported for indexed variables: "
                + ", ".join(sorted(indexed_treatments))
            )
        unknown_treatments = treated - declared
        if unknown_treatments:
            unresolved.add(
                "scenario treats undeclared variables: " + ", ".join(sorted(unknown_treatments))
            )
        scenario_fixed: dict[str, Expression] = {
            name: _scenario_literal(value)
            for name, value in scenario.fixed.items()
            if name not in indexed_values
        }
        replacements = _compose_replacements(global_replacements, scenario_fixed)
        relationships: list[RelationshipUse] = []
        parsed_definitions: dict[str, tuple[str, Expression]] = {}
        for definition in scenario.definitions:
            if definition.variable in indexed_values:
                continue
            parsed = parse_expression(definition.expression)
            if isinstance(parsed, (ParseFailure, Equation, Relationship)):
                unresolved.add(f"scenario definition for {definition.variable} is invalid")
                continue
            parsed_definitions[definition.variable] = (definition.expression, parsed)
        definition_context = WorkContext(
            definitions={},
            primitives={},
            variable_domains={
                name: declaration.domain for name, declaration in request.variables.items()
            },
        )
        qualification_result = _scenario_definition_qualifications(
            scenario,
            {name: parsed for name, (_, parsed) in parsed_definitions.items()},
            request,
            definition_context,
            global_replacements,
        )
        if isinstance(qualification_result, AnalysisFailure):
            unresolved.add(qualification_result.error.message)
            definition_qualifications: dict[str, str | None] = {}
        else:
            definition_qualifications = qualification_result
        definition_names = set(parsed_definitions)
        graph = {
            name: _symbol_names(parsed) & definition_names
            for name, (_, parsed) in parsed_definitions.items()
        }
        definition_order = _topological(graph) or ()
        definition_provenance: dict[str, set[str]] = {}
        used_definitions: set[str] = set()
        specialized = substitute_analysis(general, replacements)
        for name in definition_order:
            _, parsed = parsed_definitions[name]
            dependencies = _symbol_names(parsed) & set(definition_provenance)
            value = substitute(parsed, replacements, max_nodes=MAX_WORK_NODES)
            replacements[name] = value
            definition_provenance[name] = {name}.union(
                *(definition_provenance[dependency] for dependency in dependencies)
            )
            updated = substitute_analysis(specialized, {name: value})
            if updated != specialized:
                used_definitions.update(definition_provenance[name])
            specialized = updated
        for name in definition_order:
            source, _ = parsed_definitions[name]
            qualification = definition_qualifications.get(name)
            if name not in used_definitions:
                continue
            relationships.append(
                RelationshipUse(
                    name=f"derived:{name}",
                    relationship=f"{name} = {source}",
                )
            )
            if qualification is not None:
                unresolved.add(qualification)
        specialized = map_analysis(specialized, simplify_constants)
        expression = specialized.total_work
        relevant = _value_names(expression) & declared
        substituted_work = render_work(expression, budget)
        choice_work: dict[str, str] = {}
        choice_replacements: dict[str, dict[str, Expression]] = {}
        if scenario.fixed and not (set(scenario.fixed) & indexed_values):
            qualifications.append("fixed values substituted exactly")
        choice_names = sorted(scenario.choices)
        choice_values = [scenario.choices[name] for name in choice_names]
        if choice_names:
            for values in product(*choice_values):
                selected = dict(zip(choice_names, values, strict=True))
                value = simplify_constants(
                    substitute(
                        expression,
                        {name: _scenario_literal(item) for name, item in selected.items()},
                        max_nodes=MAX_WORK_NODES,
                    )
                )
                key = ",".join(f"{name}={selected[name]}" for name in choice_names)
                choice_work[key] = render_work(value, budget)
                choice_replacements[key] = {
                    **replacements,
                    **{name: _scenario_literal(item) for name, item in selected.items()},
                }
        if scenario.choices and not (set(scenario.choices) & indexed_values):
            qualifications.append("finite choices substituted exactly")
        asymptotic: str | None = None
        if len(scenario.asymptotic) > 1:
            unresolved.add("multivariate asymptotic dominance is unsupported")
        elif scenario.asymptotic:
            variable = scenario.asymptotic[0]
            declaration = request.variables.get(variable)
            untreated = relevant - treated
            if variable in indexed_values:
                unresolved.add(
                    f"asymptotic treatment for indexed variable {variable} is unsupported"
                )
            elif untreated:
                unresolved.add(
                    "untreated symbols block asymptotic classification: "
                    + ", ".join(sorted(untreated))
                )
            elif declaration is None or declaration.domain not in {
                MathematicalDomain.NONNEGATIVE_INTEGER,
                MathematicalDomain.POSITIVE_INTEGER,
                MathematicalDomain.POSITIVE_REAL,
            }:
                unresolved.add(f"asymptotic variable {variable} lacks a nonnegative domain")
            else:
                degree = polynomial_degree(expression, variable)
                if degree is None or not is_nondecreasing_polynomial(expression, variable):
                    unresolved.add(f"asymptotic classification for {variable} is unsupported")
                else:
                    asymptotic = (
                        "Theta(1)"
                        if degree == 0
                        else f"Theta({variable}{'**' + str(degree) if degree != 1 else ''})"
                    )
                    relationships.append(
                        RelationshipUse(
                            name=f"domain:{variable}",
                            relationship=f"{variable} in {declaration.domain.value}",
                        )
                    )
                    qualifications.append(
                        "univariate polynomial asymptotic classification uses the declared domain"
                    )
        interval: IntervalResult | None = None
        if scenario.bounds:
            if len(scenario.bounds) != 1:
                unresolved.add("multivariate interval reasoning is unsupported")
            else:
                variable, bound = next(iter(scenario.bounds.items()))
                untreated = relevant - treated
                if variable in indexed_values:
                    unresolved.add(
                        f"interval treatment for indexed variable {variable} is unsupported"
                    )
                elif untreated:
                    unresolved.add(
                        "untreated symbols block interval reasoning: "
                        + ", ".join(sorted(untreated))
                    )
                elif not is_nondecreasing_polynomial(expression, variable):
                    unresolved.add(f"monotonic interval relationship for {variable} is unproved")
                else:
                    lower = simplify_constants(
                        substitute(
                            expression,
                            {variable: _scenario_literal(bound.lower)},
                            max_nodes=MAX_WORK_NODES,
                        )
                    )
                    upper = simplify_constants(
                        substitute(
                            expression,
                            {variable: _scenario_literal(bound.upper)},
                            max_nodes=MAX_WORK_NODES,
                        )
                    )
                    lower_work = render_work(lower, budget)
                    upper_work = render_work(upper, budget)
                    interval = IntervalResult(
                        lower=str(bound.lower),
                        upper=str(bound.upper),
                        lower_inclusive=bound.lower_inclusive,
                        upper_inclusive=bound.upper_inclusive,
                        lower_work=lower_work,
                        upper_work=upper_work,
                        infimum=lower_work,
                        supremum=upper_work,
                        infimum_attained=bound.lower_inclusive,
                        supremum_attained=bound.upper_inclusive,
                    )
                    relationships.append(
                        RelationshipUse(
                            name=f"bound:{variable}",
                            relationship=(
                                f"{bound.lower} {'<=' if bound.lower_inclusive else '<'} {variable} "
                                f"{'<=' if bound.upper_inclusive else '<'} {bound.upper}"
                            ),
                        )
                    )
                    qualifications.append(
                        "interval endpoints use a proven nondecreasing univariate polynomial"
                    )
        effective_domains = _specialized_effective_domains(equations, replacements)
        choice_effective_domains: dict[str, tuple[EquationEffectiveDomains, ...]] = {}
        if choice_work:
            for key in choice_work:
                # Choice keys are canonical and this result shape intentionally uses
                # exactly the same key population as choice_work.
                choice_effective_domains[key] = _specialized_effective_domains(
                    equations, choice_replacements[key]
                )
        results.append(
            ScenarioResult(
                name=scenario.name,
                substituted_work=substituted_work,
                choice_work=choice_work,
                asymptotic=asymptotic,
                interval=interval,
                substitutions={
                    name: render_work(replacements[name], budget)
                    for name in sorted(
                        set(scenario.fixed) | {item.variable for item in scenario.definitions}
                    )
                    if name in replacements
                },
                relationships_used=(*general_relationships, *relationships),
                qualifications=tuple(qualifications),
                unresolved=tuple(sorted(unresolved)),
                effective_domains=() if choice_work else effective_domains,
                choice_effective_domains=choice_effective_domains,
            )
        )
    return tuple(results)


def _specialized_effective_domains(
    equations: tuple[ParsedEquation, ...], replacements: dict[str, Expression]
) -> tuple[EquationEffectiveDomains, ...]:
    """Render scenario-specialized analyzer domains without reparsing input text."""
    result: list[EquationEffectiveDomains] = []
    for equation in equations:
        result.append(
            EquationEffectiveDomains(
                equation=equation.name,
                domains=tuple(
                    EffectiveIndexDomain(
                        index=domain.index,
                        lower=render(
                            substitute(domain.lower, replacements, max_nodes=MAX_WORK_NODES)
                        ).sympy,
                        upper=render(
                            substitute(domain.upper, replacements, max_nodes=MAX_WORK_NODES)
                        ).sympy,
                    )
                    for domain in equation.output_domains
                ),
            )
        )
    return tuple(result)


def _equation_report(
    name: str,
    interpretation: Interpretation,
    submitted: OperationTally,
    analysis: WorkAnalysis,
    dependencies: tuple[str, ...],
    work_render_budget: WorkRenderBudget,
    relationships_used: tuple[RelationshipUse, ...] = (),
    constraints: tuple[DomainConstraint, ...] = (),
    effective_domains: tuple[EffectiveIndexDomain, ...] = (),
) -> EquationReport:
    blockers = tuple(sorted(analysis.direct_work_blockers))
    return EquationReport(
        name=name,
        interpretation=interpretation,
        operation_counts=_counts(submitted),
        aggregate_operation_counts=None
        if blockers
        else render_operations(analysis.operations, work_render_budget),
        aggregate_work=None if blockers else render_work(analysis.total_work, work_render_budget),
        direct_work_applicability="not_finite" if blockers else "finite",
        direct_work_blockers=blockers,
        dependencies=dependencies,
        primitive_invocations=None
        if blockers
        else render_invocations(analysis.invocations, work_render_budget),
        unknown_costs=tuple(sorted(analysis.unknown_costs)),
        unresolved=tuple(sorted(analysis.unresolved)),
        relationships_used=relationships_used,
        constraints=constraints,
        effective_domains=effective_domains,
        constraint_uses=tuple(
            ConstraintUse(
                equation=name,
                name=constraint.name,
                target=constraint.target,
                relationship=constraint.relationship,
            )
            for constraint in constraints
        ),
    )


def _system_report(
    equations: tuple[EquationReport, ...],
    analysis: WorkAnalysis,
    dependency_edges: tuple[tuple[str, str], ...],
    reuse: tuple[ReuseReport, ...],
    extraction_opportunities: tuple[str, ...],
    work_render_budget: WorkRenderBudget,
    relationships_used: tuple[RelationshipUse, ...] = (),
    unused_assumptions: tuple[str, ...] = (),
) -> SystemReport:
    blockers = tuple(
        f"equation {equation.name}: {blocker}"
        for equation in equations
        if equation.direct_work_blockers
        for blocker in equation.direct_work_blockers
    )
    return SystemReport(
        equations=equations,
        aggregate_operation_counts=None
        if blockers
        else render_operations(analysis.operations, work_render_budget),
        total_work=None if blockers else render_work(analysis.total_work, work_render_budget),
        direct_work_applicability="not_finite" if blockers else "finite",
        direct_work_blockers=blockers,
        dependency_edges=dependency_edges,
        reuse=reuse,
        primitive_invocations=None
        if blockers
        else render_invocations(analysis.invocations, work_render_budget),
        unknown_costs=tuple(sorted(analysis.unknown_costs)),
        unresolved=tuple(sorted(analysis.unresolved)),
        extraction_opportunities=extraction_opportunities,
        relationships_used=relationships_used,
        unused_assumptions=unused_assumptions,
    )


def _topological(edges: dict[str, set[str]]) -> list[str] | None:
    pending = {name: set(dependencies) for name, dependencies in edges.items()}
    result: list[str] = []
    while pending:
        ready = sorted(name for name, dependencies in pending.items() if not dependencies)
        if not ready:
            return None
        for name in ready:
            result.append(name)
            del pending[name]
        for dependencies in pending.values():
            dependencies.difference_update(ready)
    return result


def _scenario_domain_failure(
    request: AnalysisRequest, reasoning: ReasoningContext
) -> AnalysisFailure | None:
    def valid(value: str | int, domain: MathematicalDomain) -> bool:
        exact = _exact_fraction(value)
        if domain in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL}:
            return exact > 0 and (not domain.is_integer or exact.denominator == 1)
        if domain in {MathematicalDomain.NONNEGATIVE_INTEGER, MathematicalDomain.NONNEGATIVE_REAL}:
            return exact >= 0 and (not domain.is_integer or exact.denominator == 1)
        return not domain.is_integer or exact.denominator == 1

    for position, scenario in enumerate(request.scenarios):
        treatment_names = (
            set(scenario.fixed)
            | set(scenario.choices)
            | {item.variable for item in scenario.definitions}
            | set(scenario.asymptotic)
            | set(scenario.bounds)
        )
        missing = treatment_names - set(request.variables)
        if missing:
            name = sorted(missing)[0]
            if name in scenario.fixed:
                path = f"scenarios[{position}].fixed.{name}"
            elif name in scenario.choices:
                path = f"scenarios[{position}].choices.{name}"
            elif name in scenario.bounds:
                path = f"scenarios[{position}].bounds.{name}"
            elif name in scenario.asymptotic:
                path = f"scenarios[{position}].asymptotic[{scenario.asymptotic.index(name)}]"
            else:
                definition_position = next(
                    index
                    for index, definition in enumerate(scenario.definitions)
                    if definition.variable == name
                )
                path = f"scenarios[{position}].definitions[{definition_position}].variable"
            return _invalid(
                f"scenario {scenario.name} treats undeclared variables: "
                + ", ".join(sorted(missing)),
                source=SourceReference(path=path),
            )
        values_by_name = {
            **{name: (value,) for name, value in scenario.fixed.items()},
            **scenario.choices,
        }
        for name, values in values_by_name.items():
            declaration = request.variables.get(name)
            if declaration is not None and any(
                not valid(value, declaration.domain) for value in values
            ):
                return _invalid(
                    f"scenario {scenario.name} treatment contradicts declared domain for {name}"
                )
        for name, bound in scenario.bounds.items():
            declaration = request.variables[name]
            lower, upper = _exact_fraction(bound.lower), _exact_fraction(bound.upper)
            if declaration.domain is MathematicalDomain.POSITIVE_REAL and upper <= 0:
                return _invalid(
                    f"scenario {scenario.name} interval misses declared domain for {name}"
                )
            if declaration.domain in {
                MathematicalDomain.NONNEGATIVE_REAL,
                MathematicalDomain.NONNEGATIVE_INTEGER,
            } and (upper < 0 or (upper == 0 and not bound.upper_inclusive)):
                return _invalid(
                    f"scenario {scenario.name} interval misses declared domain for {name}"
                )
            if declaration.domain in {
                MathematicalDomain.POSITIVE_INTEGER,
                MathematicalDomain.NONNEGATIVE_INTEGER,
            }:
                least = ceil(lower) if bound.lower_inclusive else floor(lower) + 1
                greatest = floor(upper) if bound.upper_inclusive else ceil(upper) - 1
                if declaration.domain is MathematicalDomain.POSITIVE_INTEGER:
                    least = max(least, 1)
                else:
                    least = max(least, 0)
                if least > greatest:
                    return _invalid(
                        f"scenario {scenario.name} interval misses declared domain for {name}"
                    )
        choice_names = sorted(scenario.choices)
        for choice_values in product(*(scenario.choices[name] for name in choice_names)):
            replacements = {
                **{name: _scenario_literal(value) for name, value in scenario.fixed.items()},
                **{
                    name: _scenario_literal(value)
                    for name, value in zip(choice_names, choice_values, strict=True)
                },
            }
            parsed_definitions: dict[str, Expression] = {}
            for definition in scenario.definitions:
                parsed = parse_expression(definition.expression)
                if not isinstance(parsed, (ParseFailure, Equation, Relationship)):
                    parsed_definitions[definition.variable] = parsed
            definition_order = (
                _topological(
                    {
                        name: _symbol_names(value) & set(parsed_definitions)
                        for name, value in parsed_definitions.items()
                    }
                )
                or ()
            )
            for name in definition_order:
                replacements[name] = substitute(
                    parsed_definitions[name], replacements, max_nodes=MAX_WORK_NODES
                )
            for assumption in request.assumptions:
                parsed = parse_expression(assumption.relationship)
                if isinstance(parsed, Relationship):
                    truth = _literal_relationship_truth(
                        Relationship(
                            parsed.operator,
                            substitute(parsed.left, replacements, max_nodes=MAX_WORK_NODES),
                            substitute(parsed.right, replacements, max_nodes=MAX_WORK_NODES),
                        )
                    )
                    if truth is False:
                        return _invalid(
                            f"scenario {scenario.name} treatment contradicts assumption {assumption.name}"
                        )
        for name, bound in scenario.bounds.items():
            if not _interval_intersects_assumptions(name, bound, reasoning):
                return _invalid(
                    f"scenario {scenario.name} interval misses global assumptions for {name}"
                )
    return None


def _interval_intersects_assumptions(
    name: str, interval: IntervalBound, reasoning: ReasoningContext
) -> bool:
    """Check an interval against the same bounded facts used by query reasoning."""
    lower, upper = _exact_fraction(interval.lower), _exact_fraction(interval.upper)
    lower_closed, upper_closed = interval.lower_inclusive, interval.upper_inclusive
    replacement = reasoning.replacements.get(name)
    if replacement is not None:
        fixed = _constant_value(reasoning.apply(replacement))
        if fixed is not None:
            if not (
                (lower < fixed < upper)
                or (fixed == lower and lower_closed)
                or (fixed == upper and upper_closed)
            ):
                return False
            lower = upper = fixed
            lower_closed = upper_closed = True
    fact = reasoning.facts.get(name)
    if fact is None:
        return True
    if fact.lower is not None:
        if fact.lower > lower:
            lower, lower_closed = fact.lower, not fact.lower_strict
        elif fact.lower == lower:
            lower_closed = lower_closed and not fact.lower_strict
    if fact.upper is not None:
        if fact.upper < upper:
            upper, upper_closed = fact.upper, not fact.upper_strict
        elif fact.upper == upper:
            upper_closed = upper_closed and not fact.upper_strict
    if fact.integer:
        least = ceil(lower) if lower_closed else floor(lower) + 1
        greatest = floor(upper) if upper_closed else ceil(upper) - 1
        return least <= greatest
    return lower < upper or (lower == upper and lower_closed and upper_closed)


def _request_size_failure(request: AnalysisRequest) -> AnalysisFailure | None:
    try:
        sources: list[str] = []
        if request.expression is not None:
            sources.append(request.expression)
        for equation in request.equations:
            sources.append(equation.expression)
            for name, domain in equation.domains.items():
                sources.extend((name, domain.lower, domain.upper))
            for constraint in equation.constraints:
                sources.extend((constraint.name, constraint.target, constraint.relationship))
        for name in request.variables:
            sources.append(name)
        for definition in request.functions:
            sources.extend((definition.name, *definition.parameters, definition.body))
        for primitive in request.primitive_costs:
            sources.extend((primitive.name, *primitive.parameters, primitive.work))
        for assumption in request.assumptions:
            sources.extend((assumption.name, assumption.relationship))
        for definition in request.definitions:
            sources.extend((definition.variable, definition.expression))
        for query in request.queries:
            sources.append(query.name)
            if query.target is not None:
                sources.append(
                    query.target.query
                    if isinstance(query.target, DerivedTarget)
                    else query.target.name
                )
            if isinstance(query, EquivalenceQuery):
                sources.append(query.comparison)
            if isinstance(query, (LimitQuery, AsymptoticQuery)):
                sources.extend((query.variable, str(query.point)))
                if query.direction is not None:
                    sources.append(query.direction)
            if isinstance(query, PropertiesQuery):
                for check in query.checks:
                    sources.append(check.kind)
                    if isinstance(check, VariablePropertyCheck):
                        sources.append(check.variable)
        for scenario in request.scenarios:
            sources.append(scenario.name)
            for name, value in scenario.fixed.items():
                sources.extend((name, str(value)))
            for name, values in scenario.choices.items():
                sources.append(name)
                sources.extend(str(value) for value in values)
            for definition in scenario.definitions:
                sources.extend((definition.variable, definition.expression))
            sources.extend(scenario.asymptotic)
            for name, bound in scenario.bounds.items():
                sources.extend((name, str(bound.lower), str(bound.upper)))
        source_bytes = sum(len(source.encode("utf-8")) for source in sources)
    except UnicodeEncodeError:
        return AnalysisFailure(
            error=AnalysisError(
                code=AnalysisErrorCode.MALFORMED_SYNTAX,
                message="expression is not valid UTF-8",
            )
        )
    if source_bytes > MAX_REQUEST_BYTES:
        return _complexity_failure("analysis request exceeds its byte bound")
    return None


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
            outcome = outcome.model_copy(
                update={
                    "optimization": advice.model_copy(
                        update={
                            "suggestions": (),
                            "plans": (),
                            "status": "incomplete",
                            "qualifications": (
                                "optimization advice bytes budget exhausted "
                                f"(measured {advice_contribution}, "
                                f"configured {MAX_OPTIMIZATION_BYTES})",
                            ),
                        }
                    )
                }
            )
        if len(outcome.model_dump_json().encode("utf-8")) > MAX_COMBINED_RESULT_BYTES:
            return _complexity_failure("analysis result exceeds its combined size bound")
    return outcome


def _parse_failure(parsed: ParseFailure, path: str, source: str) -> AnalysisFailure:
    location = (
        SourceLocation(line=parsed.line, column=parsed.column)
        if parsed.line is not None
        and parsed.line >= 1
        and parsed.column is not None
        and parsed.column >= 0
        else None
    )
    span = (
        SourceSpan(
            start=location,
            end=SourceLocation(line=parsed.end_line, column=parsed.end_column),
        )
        if location is not None
        and parsed.end_line is not None
        and parsed.end_line >= 1
        and parsed.end_column is not None
        and parsed.end_column >= 0
        else None
    )
    alternative = (
        "use a canonical decimal such as 1.25 or an explicit division such as 5/4"
        if "decimal literal" in parsed.message
        else None
    )
    return AnalysisFailure(
        error=AnalysisError(
            code={
                ParseFailureKind.MALFORMED: AnalysisErrorCode.MALFORMED_SYNTAX,
                ParseFailureKind.UNSUPPORTED: AnalysisErrorCode.UNSUPPORTED_CONSTRUCT,
                ParseFailureKind.TOO_COMPLEX: AnalysisErrorCode.EXPRESSION_TOO_COMPLEX,
            }[parsed.kind],
            message=parsed.message,
            location=location,
            source=SourceReference(path=path, span=span, excerpt=source[:160]),
            supported_alternative=alternative,
        )
    )


def _unsupported(message: str) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(
            code=AnalysisErrorCode.UNSUPPORTED_CONSTRUCT,
            message=message,
        )
    )


def _invalid(
    message: str,
    *,
    source: SourceReference | None = None,
    supported_alternative: str | None = None,
) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(
            code=AnalysisErrorCode.INVALID_SYSTEM,
            message=message,
            source=source,
            supported_alternative=supported_alternative,
        )
    )


def _complexity_failure(message: str) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(code=AnalysisErrorCode.EXPRESSION_TOO_COMPLEX, message=message)
    )


def _normalization_failure() -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(
            code=AnalysisErrorCode.NORMALIZATION_FAILED,
            message="the validated expression could not be normalized",
        )
    )


def _counts(tally: OperationTally) -> OperationCounts:
    return OperationCounts(
        additions=tally.additions,
        subtractions=tally.subtractions,
        multiplications=tally.multiplications,
        divisions=tally.divisions,
        powers=tally.powers,
    )
