from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from py_science.formula.analyzer import OperationTally, count_operations
from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Equation,
    Expression,
    IndexedValue,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
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
    OperationCounts,
    ReuseReport,
    SourceLocation,
    SystemReport,
)
from py_science.formula.parser import ParseFailure, ParseFailureKind, parse_expression
from py_science.formula.sympy_backend import (
    NormalizationError,
    NormalizedRendering,
    render,
    render_system,
)
from py_science.formula.work import (
    FunctionRule,
    PrimitiveRule,
    WorkAnalysis,
    WorkContext,
    analyze_work,
    cardinality,
    is_integer_expression,
    render_invocations,
    render_operations,
    render_work,
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


class FormulaLoader:
    def __init__(self) -> None:
        self.nodes = 0

    def parse(self, source: str) -> Expression | Equation | AnalysisFailure:
        parsed = parse_expression(source)
        if isinstance(parsed, ParseFailure):
            return _parse_failure(parsed)
        formula_nodes = (
            expression_node_count(parsed.left) + expression_node_count(parsed.right) + 1
            if isinstance(parsed, Equation)
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
    loader = FormulaLoader()
    definitions_or_failure = _parse_definitions(request, loader)
    if isinstance(definitions_or_failure, AnalysisFailure):
        return definitions_or_failure
    definitions, primitives = definitions_or_failure
    context = WorkContext(
        definitions=definitions,
        primitives=primitives,
        variable_domains={
            name: declaration.domain for name, declaration in request.variables.items()
        },
    )
    if request.expression is not None:
        outcome = _analyze_single(request, request.expression, loader, context)
    else:
        outcome = _analyze_system(request, loader, context)
    return _bound_result(outcome)


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
        if isinstance(parsed, Equation):
            return _invalid(f"function {definition.name} body cannot contain Eq")
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
        )
    for primitive in request.primitive_costs:
        parsed = loader.parse(primitive.work)
        if isinstance(parsed, AnalysisFailure):
            return parsed
        if isinstance(parsed, Equation):
            return _invalid(f"primitive cost {primitive.name} cannot contain Eq")
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
    if _topological(graph) is None:
        return _invalid("function definitions contain a cycle")
    return None


def _analyze_single(
    request: AnalysisRequest,
    source: str,
    loader: FormulaLoader,
    context: WorkContext,
) -> AnalysisOutcome:
    parsed = loader.parse(source)
    if isinstance(parsed, AnalysisFailure):
        return parsed
    if isinstance(parsed, Equation):
        return _invalid("an ordinary expression request cannot contain Eq")
    call_failure = _check_call_arities(
        parsed,
        {
            **{name: len(rule.parameters) for name, rule in context.definitions.items()},
            **{name: len(rule.parameters) for name, rule in context.primitives.items()},
        },
        {},
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
    analysis = analyze_work(parsed, context)
    analysis.unresolved.update(index_unresolved)
    report = _equation_report(
        "expression",
        interpretation,
        tally,
        analysis,
        (),
    )
    system = _system_report((report,), WorkAnalysis().combine(analysis), (), (), ())
    return AnalysisSuccess(
        interpretation=interpretation,
        operation_counts=_counts(tally),
        abstract_work=tally.total,
        system=system,
    )


def _analyze_system(
    request: AnalysisRequest,
    loader: FormulaLoader,
    context: WorkContext,
) -> AnalysisOutcome:
    parsed_or_failure = _parse_equations(request, loader)
    if isinstance(parsed_or_failure, AnalysisFailure):
        return parsed_or_failure
    equations = parsed_or_failure
    producers_or_failure = _build_producers(equations)
    if isinstance(producers_or_failure, AnalysisFailure):
        return producers_or_failure
    producers = producers_or_failure
    validation = _validate_system(request, equations, producers, context)
    if isinstance(validation, AnalysisFailure):
        return validation
    edges, reference_counts, index_unresolved = validation
    order = _topological(edges)
    if order is None:
        return _invalid("equation dependencies contain a cycle")

    by_name = {equation.request.name: equation for equation in equations}
    render_budget = RenderingBudget()
    reports: dict[str, EquationReport] = {}
    analyses: dict[str, WorkAnalysis] = {}
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
        analysis = analyze_work(equation.formula.right, scoped_context)
        analysis.unresolved.update(index_unresolved.get(name, ()))
        for index, (lower, upper) in equation.domains.items():
            count, unresolved = cardinality(
                lower,
                upper,
                scoped_context,
                f"equation {name} output index {index}",
            )
            analysis = analysis.scale(count)
            if unresolved is not None:
                analysis.unresolved.add(unresolved)
        analyses[name] = analysis
        tally = count_operations(equation.formula.right)
        reports[name] = _equation_report(
            name,
            interpretation,
            tally,
            analysis,
            tuple(sorted(edges[name])),
        )
        all_extractions.extend(_extraction_opportunities(name, equation.formula.right, producers))

    combined = WorkAnalysis()
    for name in order:
        combined = combined.combine(analyses[name])
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
    system = _system_report(
        tuple(reports[name] for name in order),
        combined,
        tuple((dependency, name) for name in order for dependency in sorted(edges[name])),
        reuse,
        tuple(sorted(set(all_extractions))),
    )
    submitted = OperationTally()
    for name in order:
        submitted = submitted.combine(count_operations(by_name[name].formula.right))
    return AnalysisSuccess(
        interpretation=system_interpretation,
        operation_counts=_counts(submitted),
        abstract_work=submitted.total,
        system=system,
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
            if isinstance(lower, Equation) or isinstance(upper, Equation):
                return _invalid(f"equation {item.name} domain bounds cannot contain Eq")
            domains[index] = (lower, upper)
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
    unknown_arities: dict[str, int] = {}
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
            bound_error, bound_unknown = _validate_index_scopes(lower, scope, context)
            if bound_error is not None:
                return _invalid(f"equation {name} domain: {bound_error}")
            index_unknown.update(bound_unknown)
            bound_error, bound_unknown = _validate_index_scopes(upper, scope, context)
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


def _equation_report(
    name: str,
    interpretation: Interpretation,
    submitted: OperationTally,
    analysis: WorkAnalysis,
    dependencies: tuple[str, ...],
) -> EquationReport:
    return EquationReport(
        name=name,
        interpretation=interpretation,
        operation_counts=_counts(submitted),
        aggregate_operation_counts=render_operations(analysis.operations),
        aggregate_work=render_work(analysis.total_work),
        dependencies=dependencies,
        primitive_invocations=render_invocations(analysis.invocations),
        unknown_costs=tuple(sorted(analysis.unknown_costs)),
        unresolved=tuple(sorted(analysis.unresolved)),
    )


def _system_report(
    equations: tuple[EquationReport, ...],
    analysis: WorkAnalysis,
    dependency_edges: tuple[tuple[str, str], ...],
    reuse: tuple[ReuseReport, ...],
    extraction_opportunities: tuple[str, ...],
) -> SystemReport:
    return SystemReport(
        equations=equations,
        aggregate_operation_counts=render_operations(analysis.operations),
        total_work=render_work(analysis.total_work),
        dependency_edges=dependency_edges,
        reuse=reuse,
        primitive_invocations=render_invocations(analysis.invocations),
        unknown_costs=tuple(sorted(analysis.unknown_costs)),
        unresolved=tuple(sorted(analysis.unresolved)),
        extraction_opportunities=extraction_opportunities,
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
