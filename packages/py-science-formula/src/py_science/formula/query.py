# ruff: noqa: E501
# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false, reportUnusedImport=false
"""Bounded general-context query evaluation; it never contributes submitted work."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy
from py_science.formula.expressions import Expression, Relationship, RelationshipOperator
from py_science.formula.models import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisFailure,
    EquationTarget,
    EquivalenceQuery,
    ExpressionTarget,
    Interpretation,
    PropertiesQuery,
    PropertyCheck,
    QueryAnswer,
    QueryRequest,
    QueryResultBase,
    RelationshipUse,
    SourceReference,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.sympy_backend import _to_sympy, render

UNIMPLEMENTED = "query kind is not implemented in this release slice"
MAX_TARGET_NODES = 512
MAX_DEGREE = 8
MAX_EXPONENT = 32


@dataclass(frozen=True, slots=True)
class QueryTarget:
    target: ExpressionTarget | EquationTarget
    expression: Expression


def evaluate_queries(
    queries: tuple[QueryRequest, ...], target: QueryTarget, assumptions: tuple[Any, ...]
) -> tuple[QueryResultBase, ...] | AnalysisFailure:
    results: list[QueryResultBase] = []
    try:
        interpretation_render = render(target.expression)
    except Exception:
        return _failure("normalized query target cannot be rendered", "queries")
    interpretation = Interpretation(normalized_sympy=interpretation_render.sympy, normalized_latex=interpretation_render.latex)
    for position, query in enumerate(queries):
        if query.target is not None and query.target != target.target:
            # Service calls once per selected target; this catches unknown names defensively.
            return _failure("query target is unknown", f"queries[{position}].target")
        if isinstance(query, EquivalenceQuery):
            answer = _equivalence(query, target.expression, assumptions, position)
            if isinstance(answer, AnalysisFailure):
                return answer
            answers = (answer,)
        elif isinstance(query, PropertiesQuery):
            answers = tuple(_unresolved(check=item) for item in query.checks)
        else:
            answers = (_unresolved(),)
        results.append(QueryResultBase(name=query.name, kind=query.kind, target=target.target,
            normalized_target=interpretation, summary=("equivalence comparison" if query.kind == "equivalence" else UNIMPLEMENTED), answers=answers))
    return tuple(results)


def _unresolved(check: PropertyCheck | None = None) -> QueryAnswer:
    return QueryAnswer(check=check, conclusion="unresolved", blockers=(UNIMPLEMENTED,))


def _failure(message: str, path: str) -> AnalysisFailure:
    return AnalysisFailure(error=AnalysisError(code=AnalysisErrorCode.MALFORMED_SYNTAX, message=message, source=SourceReference(path=path)))


def _equivalence(query: EquivalenceQuery, expression: Expression, assumptions: tuple[Any, ...], position: int) -> QueryAnswer | AnalysisFailure:
    parsed = parse_expression(query.comparison)
    if isinstance(parsed, (ParseFailure, Relationship)):
        return _failure("equivalence comparison must be an expression", f"queries[{position}].comparison")
    try:
        lhs: Any = _to_sympy(expression)
        rhs: Any = _to_sympy(parsed)
    except Exception:
        return _unresolved_with("query family is unsupported")
    if _unsafe(lhs) or _unsafe(rhs):
        return _unresolved_with("query family is unsupported")
    used: list[RelationshipUse] = []
    substitutions: dict[Any, Any] = {}
    unsupported: list[str] = []
    for item in assumptions:
        value = item.value
        if value.operator is RelationshipOperator.EQUAL:
            left, right = _to_sympy(value.left), _to_sympy(value.right)
            if getattr(left, "is_Symbol", False):
                substitutions[left] = right
                used.append(RelationshipUse(name=item.name, relationship=item.source))
        else:
            unsupported.append(item.name)
    lhs, rhs = lhs.xreplace(substitutions), rhs.xreplace(substitutions)
    denominators = [part for part in (sympy.denom(lhs), sympy.denom(rhs)) if part != 1]
    obligations = tuple(f"{part} != 0" for part in denominators)
    try:
        difference = sympy.cancel(lhs - rhs)
        numerator, denominator = sympy.fraction(difference)
        symbols = tuple(sorted(numerator.free_symbols | denominator.free_symbols, key=str))
        poly = sympy.Poly(numerator, *symbols) if symbols else None
        if poly is not None and (poly.total_degree() > MAX_DEGREE or any(abs(int(e)) > MAX_EXPONENT for monomial in poly.monoms() for e in monomial)):
            return _unresolved_with("query polynomial exceeds its bound", unsupported)
    except Exception:
        return _unresolved_with("query family is unsupported", unsupported)
    conditions = obligations
    if numerator == 0:
        conclusion = "proved_under_assumptions" if used or conditions else "proved"
        return QueryAnswer(conclusion=conclusion, conditions=conditions, assumptions_used=tuple(used), relevant_unsupported_assumptions=tuple(unsupported), evidence={"kind":"identity", "statement":"normalized difference is zero"})
    if not symbols and numerator.is_number:
        return QueryAnswer(conclusion="disproved", conditions=conditions, assumptions_used=tuple(used), relevant_unsupported_assumptions=tuple(unsupported), evidence={"kind":"counterexample", "substitutions":{}, "target_value":str(lhs), "comparison_value":str(rhs)})
    # Deterministic small rational assignment is evidence only when all denominators remain defined.
    for integer in (0, 1, -1, 2, -2):
        values = {symbol: sympy.Rational(integer) for symbol in symbols}
        try:
            if all(part.subs(values) != 0 for part in denominators) and numerator.subs(values) != 0:
                return QueryAnswer(conclusion="disproved", conditions=conditions, assumptions_used=tuple(used), relevant_unsupported_assumptions=tuple(unsupported), evidence={"kind":"counterexample", "substitutions":{str(k):str(v) for k,v in values.items()}, "target_value":str(lhs.subs(values)), "comparison_value":str(rhs.subs(values))})
        except Exception:
            pass
    return _unresolved_with("no bounded counterexample satisfies the supported assumptions", unsupported)


def _unsafe(value: Any) -> bool:
    try:
        return sum(1 for _ in sympy.preorder_traversal(value)) > MAX_TARGET_NODES or value.has(sympy.Sum)
    except Exception:
        return True


def _unresolved_with(blocker: str, unsupported: list[str] | tuple[str, ...] = ()) -> QueryAnswer:
    return QueryAnswer(conclusion="unresolved", blockers=(blocker,), relevant_unsupported_assumptions=tuple(unsupported))
