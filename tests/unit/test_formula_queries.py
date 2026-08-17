# ruff: noqa: E501, E701
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false
import py_science.formula.sympy_backend as formula_sympy
import pytest
from py_science.formula import (
    AnalysisRequest,
    Assumption,
    CounterexampleEvidence,
    DirectedDefinition,
    EquationRequest,
    EquationTarget,
    EquivalenceResult,
    FormulaSyntax,
    FunctionDefinition,
    IdentityEvidence,
    Interpretation,
    MathematicalDomain,
    OperationCounts,
    QueryAnswer,
    SignPropertyCheck,
    VariableDeclaration,
    analyze,
)
from py_science.formula.expressions import IntegerLiteral
from py_science.formula.parser import parse_expression
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
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"properties", "checks":[{"kind":"sign", "variable":"x"}]},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"properties", "checks":[{"kind":"sign"}, {"kind":"sign"}]},))


def test_counterexamples_obey_domains_and_all_supported_assumptions():
    outcome = analyze(request(
        variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        assumptions=(
            Assumption(name="lower", relationship="x > 0"),
            Assumption(name="upper", relationship="x < 1"),
        ),
        queries=({"name":"q", "kind":"equivalence", "comparison":"0"},),
    ))
    assert outcome.status == "success"
    bounded_evidence = outcome.queries[0].answers[0].evidence
    assert isinstance(bounded_evidence, CounterexampleEvidence)
    assert bounded_evidence.substitutions == {"x": "1/2"}

    disproved = analyze(request(
        variables={"x": VariableDeclaration(domain=MathematicalDomain.POSITIVE_REAL)},
        queries=({"name":"q", "kind":"equivalence", "comparison":"0"},),
    ))
    assert disproved.status == "success"
    evidence = disproved.queries[0].answers[0].evidence
    assert isinstance(evidence, CounterexampleEvidence)
    assert evidence.substitutions["x"] in {"1", "2", "1/2"}


def test_unrelated_declared_domains_do_not_block_valid_counterexamples():
    outcome = analyze(request(
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            "unused": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        queries=({"name":"q", "kind":"equivalence", "comparison":"0"},),
    ))
    assert outcome.status == "success"
    assert outcome.queries[0].answers[0].conclusion == "disproved"


def test_equality_substitution_preserves_eliminated_symbol_domains():
    outcome = analyze(request(
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.POSITIVE_REAL),
            "y": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        assumptions=(Assumption(name="same", relationship="x == y"),),
        queries=({"name":"q", "kind":"equivalence", "comparison":"1"},),
    ))
    assert outcome.status == "success"
    evidence = outcome.queries[0].answers[0].evidence
    assert isinstance(evidence, CounterexampleEvidence)
    assert evidence.substitutions["y"] != "0"


def test_symbolic_constant_differences_require_valid_assignments():
    for expression, comparison in (("x", "x + 1"), ("1/x", "1/x + 1")):
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            queries=({"name":"q", "kind":"equivalence", "comparison":comparison},),
        ))
        assert outcome.status == "success"
        evidence = outcome.queries[0].answers[0].evidence
        assert isinstance(evidence, CounterexampleEvidence)
        assert evidence.substitutions
        if expression == "1/x":
            assert evidence.substitutions["x"] != "0"


def test_original_denominators_survive_normalization_and_use_domain_facts():
    conditional = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x/x",
        queries=({"name":"q", "kind":"equivalence", "comparison":"1"},),
    ))
    assert conditional.status == "success"
    answer = conditional.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert answer.conditions == ("x != 0",)

    qualified = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x/x",
        variables={"x": VariableDeclaration(domain=MathematicalDomain.POSITIVE_REAL)},
        assumptions=(Assumption(name="positive", relationship="x > 0"),),
        queries=({"name":"q", "kind":"equivalence", "comparison":"1"},),
    ))
    assert qualified.status == "success"
    assert qualified.queries[0].answers[0].conditions == ("x != 0",)


def test_equivalence_rejects_equations_and_relationships_with_source_identity():
    for comparison in ("Eq(x, x)", "x == x"):
        outcome = analyze(request(queries=({"name":"q", "kind":"equivalence", "comparison":comparison},)))
        assert outcome.status == "failure"
        assert outcome.error.source is not None
        assert outcome.error.source.path == "queries[0].comparison"
        assert outcome.error.source.excerpt == comparison


def test_definitions_and_safe_equalities_are_applied_with_provenance():
    outcome = analyze(request(
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            "y": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        definitions=(DirectedDefinition(variable="y", expression="x + 1"),),
        assumptions=(Assumption(name="value", relationship="2 == x"),),
        queries=({"name":"q", "kind":"equivalence", "comparison":"y - 1"},),
    ))
    assert outcome.status == "success"
    answer = outcome.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert {item.name for item in answer.assumptions_used} == {"value", "y"}


def test_later_consumers_preserve_exact_answer_shape_and_check_order():
    outcome = analyze(request(queries=(
        {"name":"p", "kind":"properties", "checks":({"kind":"sign"}, {"kind":"valid_domain", "variable":"x"})},
        {"name":"l", "kind":"limit", "variable":"x", "point":"0", "direction":"both"},
        {"name":"a", "kind":"asymptotic", "variable":"x", "point":"oo", "order":2},
    )))
    assert outcome.status == "success"
    assert [answer.check.kind for answer in outcome.queries[0].answers] == ["sign", "valid_domain"]
    assert isinstance(outcome.queries[0].answers[0].check, SignPropertyCheck)
    assert all(answer.evidence is None and answer.derived_candidates == () for result in outcome.queries for answer in result.answers)
    dumped = outcome.model_dump(mode="json")
    assert dumped["queries"][1]["answers"][0]["check"] is None
    assert dumped["queries"][1]["answers"][0]["evidence"] is None


def test_result_models_reject_wrong_evidence_and_answer_cardinality():
    interpretation = Interpretation(normalized_sympy="x", normalized_latex="x")
    answer = QueryAnswer(conclusion="proved", evidence=IdentityEvidence(statement="same"))
    EquivalenceResult(name="q", target={"kind":"expression"}, normalized_target=interpretation, summary="same", answers=(answer,))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="q", target={"kind":"expression"}, normalized_target=interpretation, summary="same", answers=(answer, answer))
    with pytest.raises(ValidationError):
        QueryAnswer(conclusion="unresolved", blockers=("unsupported",), derived_candidates=({"interpretation": interpretation, "operation_counts": OperationCounts()},))


def test_reasoning_expansion_failures_are_contained_as_unresolved():
    assumptions = tuple(
        Assumption(name=f"double{index}", relationship=f"x{index + 1} == x{index} + x{index}")
        for index in range(14)
    )
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x0",
        assumptions=assumptions,
        queries=({"name":"q", "kind":"equivalence", "comparison":"x0"},),
    ))
    assert outcome.status == "success"
    assert outcome.queries[0].answers[0].conclusion == "unresolved"
    assert outcome.queries[0].answers[0].blockers == ("query reasoning exceeds its bound",)


def test_cross_coefficient_growth_is_rejected_before_backend_calls(monkeypatch):
    denominator_a = (1 << 599) + 1
    denominator_b = (1 << 599) + 3
    parsed = parse_expression(f"1/{denominator_a} + 1/{denominator_b}")
    assert not isinstance(parsed, tuple)
    called = False

    def forbidden(_value):
        nonlocal called
        called = True
        raise AssertionError("backend conversion must remain behind the IR preflight")

    monkeypatch.setattr(formula_sympy, "_to_sympy", forbidden)
    assert formula_sympy.bounded_rational_difference(parsed, IntegerLiteral(0)) is None  # pyright: ignore[reportArgumentType]
    assert not called


def test_equivalence_resource_refusals_are_localized_unresolved():
    for comparison in ("x**9", "x**33", f"{1 << 1024}*x"):
        outcome = analyze(request(queries=({"name":"q", "kind":"equivalence", "comparison":comparison},)))
        assert outcome.status == "success"
        assert outcome.queries[0].answers[0].conclusion == "unresolved"

    nonlinear = analyze(request(
        assumptions=(Assumption(name="nonlinear", relationship="(x + 1)**8 > 0"),),
        queries=({"name":"q", "kind":"equivalence", "comparison":"x"},),
    ))
    assert nonlinear.status == "success"
    answer = nonlinear.queries[0].answers[0]
    assert answer.conclusion == "proved"
    assert answer.relevant_unsupported_assumptions == ("nonlinear",)


def test_query_sources_participate_in_whole_request_byte_accounting():
    functions = tuple(
        FunctionDefinition(name=f"f{index}", parameters=(), body="x" * 65_000)
        for index in range(4)
    )
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x",
        functions=functions,
        queries=({"name":"q", "kind":"equivalence", "comparison":"x" * 5_000},),
    ))
    assert outcome.status == "failure"
    assert outcome.error.code.value == "expression_too_complex"
    assert outcome.error.message == "analysis request exceeds its byte bound"
