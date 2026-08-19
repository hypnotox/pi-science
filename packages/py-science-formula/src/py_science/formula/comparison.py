# ruff: noqa: E501, E701, E702
# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false, reportUnusedImport=false
"""Bounded direct-Python mathematical candidate comparison."""
from __future__ import annotations

from dataclasses import replace

from py_science.formula.equivalence import equivalence_answer
from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Expression,
    IndexedValue,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
    substitute,
)
from py_science.formula.models import (
    AnalysisFailure,
    CandidateAnalysisReport,
    CandidateComparisonRequest,
    CandidateComparisonSuccess,
    CandidateOutputComparison,
    CandidateWorkComparison,
    ExpressionTarget,
    IdentityEvidence,
    Interpretation,
    PropertyEvidence,
    QueryAnswer,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.service import _analyze_computation, _AnalyzedComputation
from py_science.formula.sympy_backend import render
from py_science.formula.work import WorkRenderBudget, render_work

MAX_COMPARISON_EXPANSION_NODES = 16_384


def compare_candidates(request: CandidateComparisonRequest):
    """Compare exactly two mapped candidates without changing ordinary analysis."""
    analyzed = tuple(_analyze_computation(request.analysis_request(item)) for item in request.candidates)
    failure = next((item for item in analyzed if isinstance(item, AnalysisFailure)), None)
    if failure is not None:
        return failure
    left, right = analyzed  # type: ignore[assignment]
    reports = tuple(_report(candidate.name, result) for candidate, result in zip(request.candidates, analyzed, strict=True))
    outputs = tuple(_compare_output(mapping.name, mapping.targets, left, right, request) for mapping in request.outputs)
    semantic = _semantic_status(outputs)
    work = _work(request, reports, analyzed, semantic)
    return CandidateComparisonSuccess(candidates=reports, outputs=outputs, semantic_status=semantic, work_comparison=work)


def _report(name: str, analyzed: _AnalyzedComputation) -> CandidateAnalysisReport:
    blockers = analyzed.success.direct_work_blockers
    work = None if blockers else render_work(analyzed.aggregate_analysis.total_work, WorkRenderBudget())
    return CandidateAnalysisReport(name=name, analysis=analyzed.success, aggregate_work=work)


def _compare_output(name, targets, left, right, request) -> CandidateOutputComparison:
    operands = []
    interfaces = []
    for target, analyzed in zip(targets, (left, right), strict=True):
        operand, interface = _target_operand(target.target, analyzed)
        operands.append(operand); interfaces.append(interface)
    if None in operands:
        return _output(name, targets, "incompatible", None, QueryAnswer(conclusion="inapplicable", blockers=(next(x for x in interfaces if x),)))
    a, b = operands  # type: ignore[misc]
    # Scalar and indexed interfaces are deliberately distinct.
    if (a[1] is None) != (b[1] is None):
        return _output(name, targets, "incompatible", None, QueryAnswer(conclusion="inapplicable", blockers=("mapped outputs have incompatible scalar and indexed interfaces",)))
    if a[1] is not None and len(a[1]) != len(b[1]):
        return _output(name, targets, "incompatible", None, QueryAnswer(conclusion="inapplicable", blockers=("mapped indexed outputs have different arity",)))
    try:
        lvalue = _expand(a[0], left, {})
        rvalue = _expand(b[0], right, {})
    except Exception as error:
        return _output(name, targets, "compatible", None, QueryAnswer(conclusion="unresolved", blockers=(str(error),)))
    # positional alignment also prevents candidate-local binder spellings leaking.
    if a[1] is not None:
        names = tuple(f"comparison_index_{i}" for i in range(len(a[1])))
        lvalue = substitute(lvalue, dict(zip(a[1], (Symbol(x) for x in names), strict=True)), max_nodes=MAX_COMPARISON_EXPANSION_NODES)
        rvalue = substitute(rvalue, dict(zip(b[1], (Symbol(x) for x in names), strict=True)), max_nodes=MAX_COMPARISON_EXPANSION_NODES)
    try:
        reasoning = ReasoningContext.build(dict(request.variables), left.knowledge.definitions, left.knowledge.assumptions)
    except Exception:
        reasoning = None
    answer = equivalence_answer(lvalue, rvalue, reasoning)
    lrender, rrender = render(lvalue), render(rvalue)
    interpretations = (Interpretation(normalized_sympy=lrender.sympy, normalized_latex=lrender.latex), Interpretation(normalized_sympy=rrender.sympy, normalized_latex=rrender.latex))
    return _output(name, targets, "compatible", interpretations, answer)


def _target_operand(target, analyzed: _AnalyzedComputation):
    if isinstance(target, ExpressionTarget):
        return ((analyzed.expression, None), None) if analyzed.expression is not None else (None, "expression target requires an expression candidate")
    equation = next((item for item in analyzed.equations if item.name == target.name), None)
    if equation is None:
        return None, "mapped equation target is unknown"
    lhs = equation.formula.left
    return ((equation.formula.right, tuple(index.name for index in lhs.indices)), None) if isinstance(lhs, IndexedValue) else ((equation.formula.right, None), None)


def _expand(value: Expression, analyzed: _AnalyzedComputation, replacements: dict[str, Expression]) -> Expression:
    if expression_node_count(value) > MAX_COMPARISON_EXPANSION_NODES:
        raise ValueError("comparison expansion exceeds its aggregate node bound")
    if isinstance(value, IndexedValue) and value.name in analyzed.producers:
        producer = analyzed.producers[value.name]
        equation = next(item for item in analyzed.equations if item.name == producer.equation_name)
        lhs = equation.formula.left
        assert isinstance(lhs, IndexedValue)
        bound = dict(zip((index.name for index in lhs.indices), value.indices, strict=True))
        return _expand(substitute(equation.formula.right, bound, max_nodes=MAX_COMPARISON_EXPANSION_NODES), analyzed, replacements)
    children = expression_children(value)
    if not children: return value
    if isinstance(value, BinaryExpression): return replace(value, left=_expand(value.left, analyzed, replacements), right=_expand(value.right, analyzed, replacements))
    if isinstance(value, Sum): return replace(value, body=_expand(value.body, analyzed, replacements), lower=_expand(value.lower, analyzed, replacements), upper=_expand(value.upper, analyzed, replacements))
    if isinstance(value, Call): return replace(value, arguments=tuple(_expand(x, analyzed, replacements) for x in value.arguments))
    if isinstance(value, IndexedValue): return replace(value, indices=tuple(_expand(x, analyzed, replacements) for x in value.indices))
    return value


def _output(name, targets, interface, expanded, answer):
    return CandidateOutputComparison(name=name, targets=targets, interface_status=interface, expanded_interpretations=expanded, answer=answer.model_copy(update={"check": None, "derived_candidates": (), "constraint_uses": ()}))


def _semantic_status(outputs):
    conclusions = {item.answer.conclusion for item in outputs}
    if "disproved" in conclusions: return "disproved"
    if conclusions & {"unresolved", "inapplicable"}: return "unresolved"
    return "proved_equal_under_assumptions" if "proved_under_assumptions" in conclusions else "proved_equal"


def _work(request, reports, analyzed, semantic):
    works = tuple(item.aggregate_work for item in reports)
    base = dict(candidate_names=tuple(item.name for item in reports), candidate_works=works)
    if semantic in {"disproved", "unresolved"}:
        return CandidateWorkComparison(**base, status="not_comparable", blockers=("mapped output semantics are not established",))
    if None in works:
        return CandidateWorkComparison(**base, status="unresolved", blockers=("candidate aggregate direct work is unavailable",))
    # Exact symbolic subtraction is intentionally rendered through the bounded backend.
    from py_science.formula.expressions import BinaryOperator
    delta_expr = BinaryExpression(BinaryOperator.SUBTRACT, analyzed[1].aggregate_analysis.total_work, analyzed[0].aggregate_analysis.total_work)
    delta = render_work(delta_expr, WorkRenderBudget())
    if delta == "0":
        return CandidateWorkComparison(**base, delta=delta, status="equal", evidence=IdentityEvidence(statement="aggregate work difference is zero"))
    # Constant rendered work supports an exact fixed preference; symbolic ordering stays qualified.
    try:
        integer = int(delta)
    except ValueError:
        return CandidateWorkComparison(**base, delta=delta, status="unresolved", conditions=("exact aggregate-work sign is unsupported",), blockers=("exact factor sign chart is unsupported",))
    status = "first_lower" if integer > 0 else "second_lower"
    return CandidateWorkComparison(**base, delta=delta, status=status, evidence=PropertyEvidence(value="exact constant aggregate-work sign"))
