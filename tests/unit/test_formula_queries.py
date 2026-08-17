# ruff: noqa: E501, E701
# pyright: basic
import pytest
from py_science.formula import (
    AnalysisRequest,
    Assumption,
    EquationRequest,
    EquationTarget,
    FormulaSyntax,
    MathematicalDomain,
    VariableDeclaration,
    analyze,
)
from pydantic import ValidationError


def request(**extra):
    return AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x", **extra)


def test_equivalence_conclusions_and_empty_default():
    empty = analyze(request())
    assert empty.status == "success" and empty.queries == () and empty.abstract_work == 0
    for comparison, conclusion in (("x", "proved"), ("x + 1", "disproved"), ("Sum(x, (i, 0, 1))", "unresolved")):
        outcome = analyze(request(queries=({"name":"q", "kind":"equivalence", "comparison":comparison},)))
        assert outcome.status == "success"
        assert outcome.queries[0].answers[0].conclusion == conclusion


def test_assumption_qualification_named_rhs_and_later_consumers():
    qualified = analyze(request(variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)}, assumptions=(Assumption(name="a", relationship="x == 2"),), queries=({"name":"q", "kind":"equivalence", "comparison":"2"},)))
    assert qualified.status == "success"
    assert qualified.queries[0].answers[0].conclusion == "proved_under_assumptions"
    system = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, equations=(EquationRequest(name="value", expression="Eq(y, x + 1)"),), variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)}, queries=({"name":"q", "kind":"equivalence", "target":{"kind":"equation", "name":"value"}, "comparison":"x+1"},{"name":"later", "kind":"closed_form", "target":{"kind":"equation", "name":"value"}})))  # pyright: ignore[reportArgumentType]
    assert system.status == "success"
    assert isinstance(system.queries[0].target, EquationTarget)
    assert system.queries[0].target.name == "value"
    assert system.queries[1].answers[0].blockers == ("query kind is not implemented in this release slice",)


def test_query_contract_rejects_invalid_context_and_points():
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"equivalence", "target":{"kind":"equation", "name":"x"}, "comparison":"x"},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"limit", "variable":"x", "point":"0"},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"limit", "variable":"x", "point":"oo", "direction":"left"},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"properties", "checks":[]},))
