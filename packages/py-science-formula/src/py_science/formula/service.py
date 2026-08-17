from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import product

from py_science.formula.analyzer import OperationTally, count_operations
from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Equation,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    IntegerLiteral,
    Relationship,
    RelationshipOperator,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
    substitute,
)
from py_science.formula.models import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisRequest,
    AnalysisSuccess,
    EquationReport,
    EquationRequest,
    Interpretation,
    IntervalResult,
    MathematicalDomain,
    OperationCounts,
    RelationshipUse,
    ReuseReport,
    ScenarioResult,
    SourceLocation,
    SystemReport,
)
from py_science.formula.parser import ParseFailure, ParseFailureKind, parse_expression
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
    aggregate_analysis,
    analyze_work,
    expand_function_values,
    is_integer_expression,
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
MAX_RENDERED_BYTES = 196_608


@dataclass(frozen=True, slots=True)
class ParsedEquation:
    request: EquationRequest
    formula: Equation
    domains: dict[str, tuple[Expression, Expression]]


@dataclass(frozen=True, slots=True)
class Producer:
    equation_name: str
    value_name: str
    arity: int


@dataclass(frozen=True, slots=True)
class NamedRelationship:
    name: str
    source: str
    value: Relationship


@dataclass(frozen=True, slots=True)
class NamedDefinition:
    name: str
    source: str
    expression: Expression


@dataclass(frozen=True, slots=True)
class Knowledge:
    assumptions: tuple[NamedRelationship, ...] = ()
    definitions: tuple[NamedDefinition, ...] = ()


class FormulaLoader:
    def __init__(self) -> None:
        self.nodes = 0

    def parse(self, source: str) -> Expression | Equation | Relationship | AnalysisFailure:
        parsed = parse_expression(source)
        if isinstance(parsed, ParseFailure):
            return _parse_failure(parsed)
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
    request_failure = _request_size_failure(request)
    if request_failure is not None:
        return request_failure
    scenario_failure = _scenario_domain_failure(request)
    if scenario_failure is not None:
        return scenario_failure
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
    knowledge_or_failure = _parse_knowledge(request, loader)
    if isinstance(knowledge_or_failure, AnalysisFailure):
        return knowledge_or_failure
    knowledge = knowledge_or_failure
    try:
        if request.expression is not None:
            outcome = _analyze_single(
                request, request.expression, loader, context, request_unknown_arities, knowledge
            )
        else:
            outcome = _analyze_system(request, loader, context, request_unknown_arities, knowledge)
    except ExpressionTooComplex as error:
        return _complexity_failure(str(error))
    return _bound_result(outcome)


def _parse_knowledge(
    request: AnalysisRequest, loader: FormulaLoader
) -> Knowledge | AnalysisFailure:
    assumptions: list[NamedRelationship] = []
    for item in request.assumptions:
        parsed = loader.parse(item.relationship)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if not isinstance(parsed, Relationship):
            return _invalid(f"assumption {item.name} must be an equality or inequality")
        assumptions.append(NamedRelationship(item.name, item.relationship, parsed))
    definitions: list[NamedDefinition] = []
    for item in request.definitions:
        parsed = loader.parse(item.expression)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, (Equation, Relationship)):
            return _invalid(f"definition {item.variable} must be an expression")
        definitions.append(
            NamedDefinition(item.variable, f"{item.variable} = {item.expression}", parsed)
        )
    for scenario in request.scenarios:
        scenario_expressions: dict[str, Expression] = {}
        for definition in scenario.definitions:
            parsed = loader.parse(definition.expression)
            if isinstance(parsed, AnalysisFailure):
                return parsed
            if isinstance(parsed, (Equation, Relationship)):
                return _invalid(
                    f"scenario {scenario.name} definition "
                    f"{definition.variable} must be an expression"
                )
            scenario_expressions[definition.variable] = parsed
        scenario_names = set(scenario_expressions)
        scenario_graph = {
            name: _symbol_names(expression) & scenario_names
            for name, expression in scenario_expressions.items()
        }
        if _topological(scenario_graph) is None:
            return _invalid(f"scenario {scenario.name} definitions contain a cycle")
    graph = {
        item.name: _symbol_names(item.expression) & {other.name for other in definitions}
        for item in definitions
    }
    order = _topological(graph)
    if order is None:
        return _invalid("directed definitions contain a cycle")
    by_name = {item.name: item for item in definitions}
    contradiction = _direct_contradiction(tuple(assumptions), request)
    if contradiction is not None:
        return _invalid(contradiction)
    return Knowledge(tuple(assumptions), tuple(by_name[name] for name in order))


def _direct_contradiction(
    assumptions: tuple[NamedRelationship, ...], request: AnalysisRequest
) -> str | None:
    bounds: dict[Expression, dict[str, tuple[int, bool]]] = {}
    reverse = {
        RelationshipOperator.LESS: RelationshipOperator.GREATER,
        RelationshipOperator.LESS_EQUAL: RelationshipOperator.GREATER_EQUAL,
        RelationshipOperator.GREATER: RelationshipOperator.LESS,
        RelationshipOperator.GREATER_EQUAL: RelationshipOperator.LESS_EQUAL,
        RelationshipOperator.EQUAL: RelationshipOperator.EQUAL,
    }
    for item in assumptions:
        relation = item.value
        if isinstance(relation.right, IntegerLiteral):
            expression, value, operator = relation.left, relation.right.value, relation.operator
        elif isinstance(relation.left, IntegerLiteral):
            expression, value = relation.right, relation.left.value
            operator = reverse[relation.operator]
        else:
            continue
        entry = bounds.setdefault(expression, {})
        candidates: tuple[tuple[str, tuple[int, bool]], ...]
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
            if declaration is not None:
                domain_lower = {
                    MathematicalDomain.POSITIVE_INTEGER: (1, True),
                    MathematicalDomain.POSITIVE_REAL: (0, False),
                    MathematicalDomain.NONNEGATIVE_INTEGER: (0, True),
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
    for definition in request.functions:
        parsed = loader.parse(definition.body)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, (Equation, Relationship)):
            return _invalid(f"function {definition.name} body cannot contain a relationship")
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
    for primitive in request.primitive_costs:
        parsed = loader.parse(primitive.work)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, (Equation, Relationship)):
            return _invalid(f"primitive cost {primitive.name} cannot contain a relationship")
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
) -> AnalysisOutcome:
    parsed = loader.parse(source)
    if isinstance(parsed, AnalysisFailure):
        return parsed
    if isinstance(parsed, (Equation, Relationship)):
        return _unsupported("relationships are supported only in assumption fields")
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
        return AnalysisSuccess(
            interpretation=interpretation,
            operation_counts=_counts(tally),
            abstract_work=tally.total,
        )
    index_error, index_unresolved = _validate_index_scopes(parsed, set(), context)
    if index_error is not None:
        return _invalid(index_error)
    _bound_substitution_expansion(parsed, context.definitions)
    analysis = analyze_work(parsed, context)
    analysis.unresolved.update(index_unresolved)
    analysis, relationships = _apply_knowledge(analysis, knowledge, context.definitions)
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
    return AnalysisSuccess(
        interpretation=interpretation,
        operation_counts=_counts(tally),
        abstract_work=tally.total,
        system=system,
        scenarios=_scenario_results(request, analysis, work_render_budget, relationships),
    )


def _analyze_system(
    request: AnalysisRequest,
    loader: FormulaLoader,
    context: WorkContext,
    request_unknown_arities: dict[str, int],
    knowledge: Knowledge,
) -> AnalysisOutcome:
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

    by_name = {equation.request.name: equation for equation in equations}
    render_budget = RenderingBudget()
    work_render_budget = WorkRenderBudget()
    reports: dict[str, EquationReport] = {}
    analyses: dict[str, WorkAnalysis] = {}
    relationship_uses: dict[str, RelationshipUse] = {}
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
        for index, (lower, upper) in equation.domains.items():
            analysis, unresolved = aggregate_analysis(
                analysis,
                index,
                lower,
                upper,
                scoped_context,
                f"equation {name} output index {index}",
            )
            if unresolved is not None:
                analysis.unresolved.add(unresolved)
        analysis, used = _apply_knowledge(
            analysis, knowledge, context.definitions, report_unmatched=False
        )
        relationship_uses.update({item.name: item for item in used})
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
        )
        all_extractions.extend(_extraction_opportunities(name, equation.formula.right, producers))

    combined = WorkAnalysis()
    for name in order:
        combined = combined.combine(analyses[name])
    used_assumption_names = {
        name for name in relationship_uses if name in {item.name for item in knowledge.assumptions}
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
    used_relationships = tuple(relationship_uses[name] for name in sorted(relationship_uses))
    system = _system_report(
        tuple(reports[name] for name in order),
        combined,
        tuple((dependency, name) for name in order for dependency in sorted(edges[name])),
        reuse,
        tuple(sorted(set(all_extractions))),
        work_render_budget,
        used_relationships,
        tuple(item.name for item in knowledge.assumptions if item.name not in relationship_uses),
    )
    submitted = OperationTally()
    for name in order:
        submitted = submitted.combine(count_operations(by_name[name].formula.right))
    return AnalysisSuccess(
        interpretation=system_interpretation,
        operation_counts=_counts(submitted),
        abstract_work=submitted.total,
        system=system,
        scenarios=_scenario_results(request, combined, work_render_budget, used_relationships),
    )


def _parse_equations(
    request: AnalysisRequest,
    loader: FormulaLoader,
) -> tuple[ParsedEquation, ...] | AnalysisFailure:
    result: list[ParsedEquation] = []
    for item in request.equations:
        parsed = loader.parse(item.expression)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if not isinstance(parsed, Equation):
            return _invalid(f"equation {item.name} must use Eq(lhs, rhs)")
        lhs_indices_or_failure = _lhs_indices(parsed)
        if isinstance(lhs_indices_or_failure, AnalysisFailure):
            return lhs_indices_or_failure
        if set(item.domains) != set(lhs_indices_or_failure):
            return _invalid(f"equation {item.name} domains must exactly bind its output indices")
        domains: dict[str, tuple[Expression, Expression]] = {}
        for index, domain in item.domains.items():
            lower = loader.parse(domain.lower)
            if isinstance(lower, AnalysisFailure):
                return lower
            upper = loader.parse(domain.upper)
            if isinstance(upper, AnalysisFailure):
                return upper
            if isinstance(lower, (Equation, Relationship)) or isinstance(
                upper, (Equation, Relationship)
            ):
                return _invalid(f"equation {item.name} domain bounds cannot contain Eq")
            domains[index] = (lower, upper)
        output_indices = set(domains)
        for lower, upper in domains.values():
            dependent = (_symbol_names(lower) | _symbol_names(upper)) & output_indices
            if dependent:
                return _invalid(
                    f"equation {item.name} output-domain bounds cannot depend on output indices: "
                    + ", ".join(sorted(dependent))
                )
        result.append(ParsedEquation(item, parsed, domains))
    return tuple(result)


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
        producers[value_name] = Producer(equation.request.name, value_name, arity)
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
    edges: dict[str, set[str]] = {equation.request.name: set() for equation in equations}
    references: dict[tuple[str, str], int] = defaultdict(int)
    unresolved: dict[str, tuple[str, ...]] = {}
    known_arities = {
        **{name: len(rule.parameters) for name, rule in context.definitions.items()},
        **{name: len(rule.parameters) for name, rule in context.primitives.items()},
    }
    unknown_arities = dict(request_unknown_arities)
    external: set[str] = set()
    producer_names = set(producers)
    for equation in equations:
        name = equation.request.name
        scope = set(equation.domains)
        index_error, index_unknown = _validate_index_scopes(
            equation.formula.right,
            scope,
            context,
        )
        if index_error is not None:
            return _invalid(f"equation {name}: {index_error}")
        for lower, upper in equation.domains.values():
            for bound in (lower, upper):
                referenced_producers = _referenced_producers(bound, producers)
                if referenced_producers:
                    return _invalid(
                        f"equation {name} output-domain bounds cannot reference named results: "
                        + ", ".join(sorted(referenced_producers))
                    )
                call_failure = _check_call_arities(bound, known_arities, unknown_arities)
                if call_failure is not None:
                    return call_failure
                bound_error, bound_unknown = _validate_index_scopes(bound, scope, context)
                if bound_error is not None:
                    return _invalid(f"equation {name} domain: {bound_error}")
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
        call_stack=context.call_stack,
    )
    unresolved: set[str] = set()
    if isinstance(expression, IndexedValue):
        for index in expression.indices:
            used = _symbol_names(index)
            out_of_scope = used - scope
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
    if isinstance(expression, Symbol):
        return {expression.name}
    result: set[str] = set()
    for child in expression_children(expression):
        result.update(_symbol_names(child))
    return result


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


def _contains_advanced(expression: Expression) -> bool:
    if isinstance(expression, (IndexedValue, Call, Sum)):
        return True
    return any(_contains_advanced(child) for child in expression_children(expression))


def _extraction_opportunities(
    equation_name: str,
    expression: Expression,
    producers: dict[str, Producer],
) -> tuple[str, ...]:
    counts: Counter[Expression] = Counter()

    def visit(node: Expression) -> None:
        is_named_reference = (isinstance(node, Symbol) and node.name in producers) or (
            isinstance(node, IndexedValue) and node.name in producers
        )
        if isinstance(node, (BinaryExpression, Call, Sum)) and not is_named_reference:
            counts[node] += 1
        for child in expression_children(node):
            visit(child)

    visit(expression)
    opportunities: list[str] = []
    for node, count in counts.items():
        if count > 1:
            try:
                text = render(node).sympy
            except NormalizationError:
                continue
            opportunities.append(
                f"equation {equation_name}: extract repeated `{text}` ({count} occurrences)"
            )
    return tuple(sorted(opportunities))


def _apply_knowledge(
    analysis: WorkAnalysis,
    knowledge: Knowledge,
    function_definitions: dict[str, FunctionRule],
    *,
    report_unmatched: bool = True,
) -> tuple[WorkAnalysis, tuple[RelationshipUse, ...]]:
    result = analysis
    uses: list[RelationshipUse] = []
    replacements: dict[str, Expression] = {}
    definition_provenance: dict[str, set[str]] = {}
    used_definitions: set[str] = set()
    for definition in knowledge.definitions:
        dependencies = _symbol_names(definition.expression) & set(replacements)
        expression = substitute(definition.expression, replacements, max_nodes=MAX_WORK_NODES)
        replacements[definition.name] = expression
        definition_provenance[definition.name] = {definition.name}.union(
            *(definition_provenance[name] for name in dependencies)
        )
        updated = substitute_analysis(result, {definition.name: expression})
        if updated != result:
            used_definitions.update(definition_provenance[definition.name])
        result = updated
    for definition in knowledge.definitions:
        if definition.name in used_definitions:
            uses.append(
                RelationshipUse(
                    name=f"definition:{definition.name}", relationship=definition.source
                )
            )
    for assumption in knowledge.assumptions:
        relation = assumption.value
        if relation.operator is not RelationshipOperator.EQUAL:
            result.unresolved.add(
                f"assumption {assumption.name}: inequality inference is unsupported"
            )
            continue
        changed = False
        if expression_node_count(relation.left) >= expression_node_count(relation.right):
            target, replacement = relation.left, relation.right
        else:
            target, replacement = relation.right, relation.left

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


def _scenario_results(
    request: AnalysisRequest,
    general: WorkAnalysis,
    budget: WorkRenderBudget,
    general_relationships: tuple[RelationshipUse, ...],
) -> tuple[ScenarioResult, ...]:
    results: list[ScenarioResult] = []
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
        replacements: dict[str, Expression] = {
            name: IntegerLiteral(value)
            for name, value in scenario.fixed.items()
            if name not in indexed_values
        }
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
        definition_names = set(parsed_definitions)
        graph = {
            name: _symbol_names(parsed) & definition_names
            for name, (_, parsed) in parsed_definitions.items()
        }
        for name in _topological(graph) or ():
            source, parsed = parsed_definitions[name]
            value = substitute(parsed, replacements, max_nodes=MAX_WORK_NODES)
            replacements[name] = value
            relationships.append(
                RelationshipUse(
                    name=f"derived:{name}",
                    relationship=f"{name} = {source}",
                )
            )
        specialized = map_analysis(substitute_analysis(general, replacements), simplify_constants)
        expression = specialized.total_work
        relevant = _value_names(expression) & declared
        substituted_work = render_work(expression, budget)
        choice_work: dict[str, str] = {}
        if scenario.fixed and not (set(scenario.fixed) & indexed_values):
            qualifications.append("fixed values substituted exactly")
        choice_names = sorted(scenario.choices)
        choice_values = [scenario.choices[name] for name in choice_names]
        for values in product(*choice_values):
            selected = dict(zip(choice_names, values, strict=True))
            value = simplify_constants(
                substitute(
                    expression,
                    {name: IntegerLiteral(item) for name, item in selected.items()},
                    max_nodes=MAX_WORK_NODES,
                )
            )
            key = ",".join(f"{name}={selected[name]}" for name in choice_names)
            choice_work[key] = render_work(value, budget)
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
                elif bound.lower < 0 or not is_nondecreasing_polynomial(expression, variable):
                    unresolved.add(f"monotonic interval relationship for {variable} is unproved")
                else:
                    lower = simplify_constants(
                        substitute(
                            expression,
                            {variable: IntegerLiteral(bound.lower)},
                            max_nodes=MAX_WORK_NODES,
                        )
                    )
                    upper = simplify_constants(
                        substitute(
                            expression,
                            {variable: IntegerLiteral(bound.upper)},
                            max_nodes=MAX_WORK_NODES,
                        )
                    )
                    interval = IntervalResult(
                        lower_work=render_work(lower, budget), upper_work=render_work(upper, budget)
                    )
                    relationships.append(
                        RelationshipUse(
                            name=f"bound:{variable}",
                            relationship=f"{bound.lower} <= {variable} <= {bound.upper}",
                        )
                    )
                    qualifications.append(
                        "interval endpoints use a proven nondecreasing univariate polynomial"
                    )
        results.append(
            ScenarioResult(
                name=scenario.name,
                substituted_work=substituted_work,
                choice_work=choice_work,
                asymptotic=asymptotic,
                interval=interval,
                substitutions={
                    name: render_work(value, budget) for name, value in sorted(replacements.items())
                },
                relationships_used=(*general_relationships, *relationships),
                qualifications=tuple(qualifications),
                unresolved=tuple(sorted(unresolved)),
            )
        )
    return tuple(results)


def _equation_report(
    name: str,
    interpretation: Interpretation,
    submitted: OperationTally,
    analysis: WorkAnalysis,
    dependencies: tuple[str, ...],
    work_render_budget: WorkRenderBudget,
    relationships_used: tuple[RelationshipUse, ...] = (),
) -> EquationReport:
    return EquationReport(
        name=name,
        interpretation=interpretation,
        operation_counts=_counts(submitted),
        aggregate_operation_counts=render_operations(analysis.operations, work_render_budget),
        aggregate_work=render_work(analysis.total_work, work_render_budget),
        dependencies=dependencies,
        primitive_invocations=render_invocations(analysis.invocations, work_render_budget),
        unknown_costs=tuple(sorted(analysis.unknown_costs)),
        unresolved=tuple(sorted(analysis.unresolved)),
        relationships_used=relationships_used,
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
    return SystemReport(
        equations=equations,
        aggregate_operation_counts=render_operations(analysis.operations, work_render_budget),
        total_work=render_work(analysis.total_work, work_render_budget),
        dependency_edges=dependency_edges,
        reuse=reuse,
        primitive_invocations=render_invocations(analysis.invocations, work_render_budget),
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


def _scenario_domain_failure(request: AnalysisRequest) -> AnalysisFailure | None:
    def valid(value: int, domain: MathematicalDomain) -> bool:
        if domain in {MathematicalDomain.POSITIVE_INTEGER, MathematicalDomain.POSITIVE_REAL}:
            return value > 0
        if domain is MathematicalDomain.NONNEGATIVE_INTEGER:
            return value >= 0
        return True

    for scenario in request.scenarios:
        treatment_names = (
            set(scenario.fixed)
            | set(scenario.choices)
            | {item.variable for item in scenario.definitions}
            | set(scenario.asymptotic)
            | set(scenario.bounds)
        )
        missing = treatment_names - set(request.variables)
        if missing:
            return _invalid(
                f"scenario {scenario.name} treats undeclared variables: "
                + ", ".join(sorted(missing))
            )
        values_by_name = {
            **{name: (value,) for name, value in scenario.fixed.items()},
            **scenario.choices,
            **{name: (bound.lower, bound.upper) for name, bound in scenario.bounds.items()},
        }
        for name, values in values_by_name.items():
            declaration = request.variables.get(name)
            if declaration is not None and any(
                not valid(value, declaration.domain) for value in values
            ):
                return _invalid(
                    f"scenario {scenario.name} treatment contradicts declared domain for {name}"
                )
    return None


def _request_size_failure(request: AnalysisRequest) -> AnalysisFailure | None:
    try:
        sources: list[str] = []
        if request.expression is not None:
            sources.append(request.expression)
        for equation in request.equations:
            sources.append(equation.expression)
            for name, domain in equation.domains.items():
                sources.extend((name, domain.lower, domain.upper))
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
    if (
        isinstance(outcome, AnalysisSuccess)
        and len(outcome.model_dump_json().encode("utf-8")) > MAX_RESULT_BYTES
    ):
        return _complexity_failure("analysis result exceeds its size bound")
    return outcome


def _parse_failure(parsed: ParseFailure) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(
            code={
                ParseFailureKind.MALFORMED: AnalysisErrorCode.MALFORMED_SYNTAX,
                ParseFailureKind.UNSUPPORTED: AnalysisErrorCode.UNSUPPORTED_CONSTRUCT,
                ParseFailureKind.TOO_COMPLEX: AnalysisErrorCode.EXPRESSION_TOO_COMPLEX,
            }[parsed.kind],
            message=parsed.message,
            location=(
                SourceLocation(line=parsed.line, column=parsed.column)
                if parsed.line is not None
                and parsed.line >= 1
                and parsed.column is not None
                and parsed.column >= 0
                else None
            ),
        )
    )


def _unsupported(message: str) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(
            code=AnalysisErrorCode.UNSUPPORTED_CONSTRUCT,
            message=message,
            location=SourceLocation(line=1, column=0),
        )
    )


def _invalid(message: str) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(code=AnalysisErrorCode.INVALID_SYSTEM, message=message)
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
