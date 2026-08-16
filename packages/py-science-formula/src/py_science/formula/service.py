# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportIndexIssue=false, reportUnusedImport=false
from py_science.formula.analyzer import OperationTally, count_operations
from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Equation,
    Expression,
    IndexedValue,
    Sum,
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
    PrimitiveCost,
    SourceLocation,
    SystemReport,
)
from py_science.formula.parser import ParseFailure, ParseFailureKind, parse_expression
from py_science.formula.sympy_backend import NormalizationError, render


def analyze(request: AnalysisRequest) -> AnalysisOutcome:
    if request.expression is not None:
        return _single(request.expression)
    return _system(request)


def _single(source: str) -> AnalysisOutcome:
    parsed = parse_expression(source)
    if isinstance(parsed, ParseFailure):
        return _failure(parsed)
    if isinstance(parsed, Equation):
        return _invalid("an ordinary expression request cannot contain Eq")
    try:
        normalized = render(parsed)
    except NormalizationError:
        return AnalysisFailure(
            error=AnalysisError(
                code=AnalysisErrorCode.NORMALIZATION_FAILED,
                message="the validated expression could not be normalized",
            )
        )
    tally = count_operations(parsed)
    return AnalysisSuccess(
        interpretation=Interpretation(
            normalized_sympy=normalized.sympy, normalized_latex=normalized.latex
        ),
        operation_counts=_counts(tally),
        abstract_work=tally.total,
    )


def _system(request: AnalysisRequest) -> AnalysisOutcome:
    parsed: list[tuple[EquationRequest, Equation]] = []
    for item in request.equations:
        result = parse_expression(item.expression)
        if isinstance(result, ParseFailure):
            return _failure(result)
        if not isinstance(result, Equation):
            return _invalid(f"equation {item.name} must use Eq(lhs, rhs)")
        if set(item.domains) != set(_lhs_indices(result)):
            return _invalid(f"equation {item.name} domains must exactly bind its output indices")
        parsed.append((item, result))
    producers = {equation.left.name: item.name for item, equation in parsed}
    edges: dict[str, set[str]] = {item.name: set() for item, _ in parsed}
    for item, equation in parsed:
        for reference in _indexed_references(equation.right):
            producer = producers.get(reference)
            if producer:
                if producer == item.name:
                    return _invalid(f"equation {item.name} references itself")
                edges[item.name].add(producer)
    order = _topological(edges)
    if order is None:
        return _invalid("equation dependencies contain a cycle")
    reports: dict[str, EquationReport] = {}
    unknown: set[str] = set()
    function_names = {f.name for f in request.functions}
    primitive = {p.name: p for p in request.primitive_costs}
    for name in order:
        item, equation = next(pair for pair in parsed if pair[0].name == name)
        if not _indexes_scoped(equation.right, set(item.domains)):
            return _invalid(f"equation {name} has an out-of-scope index")
        try:
            normalized = render(equation)
        except NormalizationError:
            return AnalysisFailure(
                error=AnalysisError(
                    code=AnalysisErrorCode.NORMALIZATION_FAILED,
                    message="the validated expression could not be normalized",
                )
            )
        tally = count_operations(equation.right)
        work = _work(equation.right, primitive, function_names, unknown)
        for domain in item.domains.values():
            work = f"({work})*Max(({domain.upper}) - ({domain.lower}) + 1, 0)"
        reports[name] = EquationReport(
            name=name,
            interpretation=Interpretation(
                normalized_sympy=normalized.sympy, normalized_latex=normalized.latex
            ),
            operation_counts=_counts(tally),
            aggregate_work=work,
            dependencies=tuple(sorted(edges[name])),
        )
    total = " + ".join(f"({reports[name].aggregate_work})" for name in order) or "0"
    first = reports[order[0]]
    return AnalysisSuccess(
        interpretation=first.interpretation,
        operation_counts=first.operation_counts,
        abstract_work=first.operation_counts.additions
        + first.operation_counts.subtractions
        + first.operation_counts.multiplications
        + first.operation_counts.divisions
        + first.operation_counts.powers,
        system=SystemReport(
            equations=tuple(reports[n] for n in order),
            total_work=total,
            dependency_edges=tuple(
                (dependency, name) for name in order for dependency in sorted(edges[name])
            ),
            unknown_costs=tuple(sorted(unknown)),
            unresolved=tuple(f"unknown cost for {x}" for x in sorted(unknown)),
        ),
    )


def _work(
    expr: Expression, primitive: dict[str, PrimitiveCost], definitions: set[str], unknown: set[str]
) -> str:
    tally = count_operations(expr)
    if isinstance(expr, Sum):
        card = f"Max(({_text(expr.upper)}) - ({_text(expr.lower)}) + 1, 0)"
        body = _work(expr.body, primitive, definitions, unknown)
        return f"({card})*({body}) + Max(({card}) - 1, 0)"
    if isinstance(expr, Call):
        args = " + ".join(_work(arg, primitive, definitions, unknown) for arg in expr.arguments)
        if expr.name in definitions:
            return f"({args}) + work({expr.name})"
        if expr.name in primitive:
            return f"({args}) + ({primitive[expr.name].work})"
        unknown.add(expr.name)
        return f"({args}) + C_{expr.name}"
    return str(tally.total)


def _text(expr: Expression) -> str:
    try:
        return render(expr).sympy
    except NormalizationError:
        return "?"


def _lhs_indices(equation: Equation) -> tuple[str, ...]:
    return (
        tuple(index.name for index in equation.left.indices if hasattr(index, "name"))
        if isinstance(equation.left, IndexedValue)
        else ()
    )


def _indexed_references(expr: Expression) -> set[str]:
    if isinstance(expr, IndexedValue):
        return {expr.name} | set().union(*(_indexed_references(x) for x in expr.indices))
    if isinstance(expr, BinaryExpression):
        return _indexed_references(expr.left) | _indexed_references(expr.right)
    if isinstance(expr, Call):
        return (
            set().union(*(_indexed_references(x) for x in expr.arguments))
            if expr.arguments
            else set()
        )
    if isinstance(expr, Sum):
        return (
            _indexed_references(expr.body)
            | _indexed_references(expr.lower)
            | _indexed_references(expr.upper)
        )
    return set()


def _indexes_scoped(expr: Expression, scope: set[str]) -> bool:
    if isinstance(expr, IndexedValue):
        return all(not hasattr(i, "name") or i.name in scope for i in expr.indices)
    if isinstance(expr, BinaryExpression):
        return _indexes_scoped(expr.left, scope) and _indexes_scoped(expr.right, scope)
    if isinstance(expr, Call):
        return all(_indexes_scoped(i, scope) for i in expr.arguments)
    if isinstance(expr, Sum):
        return (
            _indexes_scoped(expr.lower, scope)
            and _indexes_scoped(expr.upper, scope)
            and _indexes_scoped(expr.body, scope | {expr.index})
        )
    return True


def _topological(edges: dict[str, set[str]]) -> list[str] | None:
    pending = {name: set(deps) for name, deps in edges.items()}
    result = []
    while pending:
        ready = sorted(name for name, deps in pending.items() if not deps)
        if not ready:
            return None
        for name in ready:
            result.append(name)
            del pending[name]
        for deps in pending.values():
            deps.difference_update(ready)
    return result


def _failure(parsed: ParseFailure) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(
            code={
                ParseFailureKind.MALFORMED: AnalysisErrorCode.MALFORMED_SYNTAX,
                ParseFailureKind.UNSUPPORTED: AnalysisErrorCode.UNSUPPORTED_CONSTRUCT,
                ParseFailureKind.TOO_COMPLEX: AnalysisErrorCode.EXPRESSION_TOO_COMPLEX,
            }[parsed.kind],
            message=parsed.message,
            location=SourceLocation(line=parsed.line, column=parsed.column)
            if parsed.line and parsed.column is not None
            else None,
        )
    )


def _invalid(message: str) -> AnalysisFailure:
    return AnalysisFailure(
        error=AnalysisError(code=AnalysisErrorCode.INVALID_SYSTEM, message=message)
    )


def _counts(t: OperationTally) -> OperationCounts:
    return OperationCounts(
        additions=t.additions,
        subtractions=t.subtractions,
        multiplications=t.multiplications,
        divisions=t.divisions,
        powers=t.powers,
    )
