# ruff: noqa: E501, E701
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false
import py_science.formula.query as formula_query
import py_science.formula.series as formula_series
import py_science.formula.sympy_backend as formula_sympy
import py_science.formula.sympy_backend as sympy_backend
import pytest
from py_science.formula import (
    AnalysisRequest,
    Assumption,
    CounterexampleEvidence,
    DirectedDefinition,
    EquationRequest,
    EquationTarget,
    EquivalenceQuery,
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
from py_science.formula.query import QueryTarget
from py_science.formula.reasoning import ReasoningContext
from pydantic import ValidationError


def request(**extra):
    return AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x", **extra)


def test_bounded_integer_power_identities_normalize_in_query_backend():
    for expression, comparison, conditions in (
        ("x**2", "x*x", ()),
        ("(x+1)**2", "x**2 + 2*x + 1", ()),
        ("(x**2-1)/(x-1)", "x+1", ("x - 1 != 0",)),
        ("x**-1", "1/x", ("x != 0",)),
    ):
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            queries=({"name":"q", "kind":"equivalence", "comparison":comparison},),
        ))
        assert outcome.status == "success"
        answer = outcome.queries[0].answers[0]
        assert answer.conclusion in {"proved", "proved_under_assumptions"}
        assert answer.conditions == conditions


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
    assert system.queries[1].answers[0].blockers == (
        "closed-form expression has no sibling sums; use one to eight sibling "
        "(a*k+b)*r**k sums",
    )


def test_closed_form_series_rule_matrix_and_afmm_identity():
    afmm = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum((k + 1) * q**k, (k, p, oo))",
        variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER), "q": VariableDeclaration(domain=MathematicalDomain.REAL)},
        assumptions=(Assumption(name="q_nonnegative", relationship="q >= 0"), Assumption(name="q_converges", relationship="q < 1")),
        queries=({"name": "tail", "kind": "closed_form"},),
    ))
    assert afmm.status == "success"
    answer = afmm.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert answer.evidence is not None and answer.evidence.kind == "closed_form"
    assert answer.evidence.verification == "infinite_partial_sum"  # pyright: ignore[reportAttributeAccessIssue]
    assert {item.name for item in answer.assumptions_used} == {"q_nonnegative", "q_converges"}
    assert "q**p" in answer.derived_candidates[0].interpretation.normalized_sympy

    finite = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(k * 2**k, (k, 0, 3))", queries=({"name": "finite", "kind": "closed_form"},)))
    assert finite.status == "success"
    assert finite.queries[0].answers[0].evidence is not None
    assert finite.queries[0].answers[0].evidence.kind == "closed_form"
    assert finite.queries[0].answers[0].evidence.verification == "finite_antidifference"  # pyright: ignore[reportAttributeAccessIssue]
    assert finite.queries[0].answers[0].derived_candidates[0].interpretation.normalized_sympy == "34"

    for expression, conclusion, blocker in (("Sum(k * 2**k, (k, 0, oo))", "inapplicable", None), ("Sum(k * q**k, (k, 0, oo))", "unresolved", "series convergence is not proved"), ("Sum(Sum(k * q**k, (k, 0, 1)), (j, 0, 1))", "unresolved", "nested sums are unsupported"), ("Sum(k**2 * q**k, (k, 0, 1))", "unresolved", "closed-form summand does not match (a*k+b)*r**k; use a summand in that form")):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression, queries=({"name": "series", "kind": "closed_form"},)))
        assert outcome.status == "success"
        terminal = outcome.queries[0].answers[0]
        assert terminal.conclusion == conclusion
        if blocker is not None: assert terminal.blockers == (blocker,)
    empty = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(k * q**k, (k, 2, 1))", queries=({"name": "empty", "kind": "closed_form"},)))
    assert empty.status == "success"
    assert empty.queries[0].answers[0].conclusion == "proved_under_assumptions"
    assert empty.queries[0].answers[0].derived_candidates[0].interpretation.normalized_sympy == "0"


def test_closed_form_uses_affine_facts_domain_obligations_and_bounded_collection():
    symbolic = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*q**k, (k, 0, n))",
        variables={"n": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)},
        assumptions=(Assumption(name="ratio_below_one", relationship="q < 1"),),
        queries=({"name": "finite", "kind": "closed_form"},),
    ))
    assert symbolic.status == "success"
    answer = symbolic.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert {use.name for use in answer.assumptions_used} == {"ratio_below_one"}
    assert "q != 1" in answer.conditions

    collected = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*q**k + q**k, (k, 0, 2))",
        assumptions=(Assumption(name="q_above_one", relationship="q > 1"),),
        queries=({"name": "collected", "kind": "closed_form"},),
    ))
    assert collected.status == "success"
    assert collected.queries[0].answers[0].conclusion == "proved_under_assumptions"

    unresolved = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*q**k, (k, p, 3))",
        variables={"p": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        assumptions=(Assumption(name="p_before", relationship="p <= 3"), Assumption(name="q_not_one", relationship="q < 1")),
        queries=({"name": "negative", "kind": "closed_form"},),
    ))
    assert unresolved.status == "success"
    assert unresolved.queries[0].answers[0].blockers == ("series ratio is not proved nonzero for a negative exponent range",)
    discharged = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*q**k, (k, p, 3))",
        variables={"p": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        assumptions=(Assumption(name="p_before", relationship="p <= 3"), Assumption(name="q_nonzero", relationship="q > 0"), Assumption(name="q_not_one", relationship="q < 1")),
        queries=({"name": "negative", "kind": "closed_form"},),
    ))
    assert discharged.status == "success"
    answer = discharged.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert "q != 0" in answer.conditions
    assert {use.name for use in answer.assumptions_used} == {"p_before", "q_nonzero", "q_not_one"}


def test_closed_form_never_labels_an_unverified_candidate_proved(monkeypatch):
    monkeypatch.setattr(formula_sympy, "bounded_series_verify", lambda *args, **kwargs: False)
    monkeypatch.setattr("py_science.formula.series.bounded_series_verify", lambda *args, **kwargs: False)
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*2**k, (k, 0, 3))",
        queries=({"name": "finite", "kind": "closed_form"},),
    ))
    assert outcome.status == "success"
    answer = outcome.queries[0].answers[0]
    assert answer.conclusion == "unresolved"
    assert answer.evidence is None and answer.derived_candidates == ()
    assert answer.blockers == ("series antidifference verification failed",)


def test_closed_form_residual_verification_domain_preflight_normalization_and_provenance(monkeypatch):
    original_candidate = formula_series.bounded_series_candidate

    def candidate_plus_one(*args, **kwargs):
        candidate = original_candidate(*args, **kwargs)
        assert candidate is not None
        return candidate + 1

    monkeypatch.setattr(formula_series, "bounded_series_candidate", candidate_plus_one)
    for expression, blocker in (
        ("Sum(k*2**k, (k, 0, 3))", "series antidifference verification failed"),
        ("Sum(k*q**k, (k, 0, oo))", "series partial-sum verification failed"),
    ):
        extra = (
            {"variables": {"q": VariableDeclaration(domain=MathematicalDomain.REAL)},
             "assumptions": (Assumption(name="converges", relationship="q > 0"), Assumption(name="below_one", relationship="q < 1"))}
            if "oo" in expression else {}
        )
        result = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY, expression=expression,
            queries=({"name": "closed", "kind": "closed_form"},), **extra,
        ))
        assert result.status == "success"
        assert result.queries[0].answers[0].blockers == (blocker,)

    monkeypatch.undo()
    # A submitted denominator remains an obligation: q=-1 makes the original
    # finite geometric sum zero and may not become an unconditional 1.
    denominator = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(q**k, (k, 0, 1))/Sum(q**k, (k, 0, 1))",
        assumptions=(Assumption(name="q_is_minus_one", relationship="q == -1"),),
        queries=({"name": "closed", "kind": "closed_form"},),
    ))
    assert denominator.status == "success"
    assert denominator.queries[0].answers[0].blockers == ("original denominator is not proved nonzero",)

    for expression in ("Sum(k*q**k-q**k, (k, 0, 2))", "Sum(2*(k*q**k+q**k), (k, 0, 2))"):
        normalized = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY, expression=expression,
            assumptions=(Assumption(name="ratio_not_one", relationship="q < 1"),),
            queries=({"name": "closed", "kind": "closed_form"},),
        ))
        assert normalized.status == "success"
        assert normalized.queries[0].answers[0].conclusion == "proved_under_assumptions"

    provenance = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*r**k, (k, 0, 3))",
        assumptions=(Assumption(name="ratio_value", relationship="r == 2"),),
        queries=({"name": "closed", "kind": "closed_form"},),
    ))
    assert provenance.status == "success"
    assert {use.name for use in provenance.queries[0].answers[0].assumptions_used} == {"ratio_value"}


def test_closed_form_exponent_preflight_precedes_series_backend(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("series backend/render must remain behind shell preflight")

    monkeypatch.setattr(formula_series, "render", forbidden)
    monkeypatch.setattr(formula_series, "bounded_series_candidate", forbidden)
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="Sum(k*2**k, (k, 0, 3))**33",
        queries=({"name": "closed", "kind": "closed_form"},),
    ))
    assert outcome.status == "success"
    assert outcome.queries[0].answers[0].blockers == (
        "closed-form shell exceeds its bounded exponent limit: observed 33, configured 32; "
        "simplify the enclosing arithmetic",
    )


def test_closed_form_reports_each_public_family_refusal():
    def blocker(expression: str) -> str:
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            queries=({"name": "closed", "kind": "closed_form"},),
        ))
        assert outcome.status == "success"
        answer = outcome.queries[0].answers[0]
        assert answer.conclusion == "unresolved"
        assert len(answer.blockers) == 1
        return answer.blockers[0]

    target_terms = ["x"] * 257
    while len(target_terms) > 1:
        target_terms = [
            f"({target_terms[index]} + {target_terms[index + 1]})"
            if index + 1 < len(target_terms)
            else target_terms[index]
            for index in range(0, len(target_terms), 2)
        ]
    oversized_target = target_terms[0]
    sibling_sums = " + ".join(f"Sum(k*{index + 2}**k, (k, 0, 1))" for index in range(9))
    for expression, expected in (
        (
            oversized_target,
            "closed-form target exceeds its bounded node limit: observed 513, configured 512; "
            "simplify the target",
        ),
        (
            "x",
            "closed-form expression has no sibling sums; use one to eight sibling "
            "(a*k+b)*r**k sums",
        ),
        (
            sibling_sums,
            "closed-form expression has too many sibling sums: observed 9, configured 8; "
            "use one to eight sibling (a*k+b)*r**k sums",
        ),
        (
            "Sum(k*q**k, (k, 0, -oo))",
            "closed-form sum has a negative-infinity upper bound; use a finite upper "
            "bound or positive infinity",
        ),
        (
            "Sum(sin(k)*q**k, (k, 0, 1))",
            "closed-form summand contains forbidden structure; use bounded arithmetic "
            "over the summation index",
        ),
        (
            "Sum(k*q**k, (k, k, 3))",
            "closed-form sum bounds depend on the summation index; use index-independent bounds",
        ),
        (
            "Sum(k**2*q**k, (k, 0, 1))",
            "closed-form summand does not match (a*k+b)*r**k; use a summand in that form",
        ),
    ):
        assert blocker(expression) == expected


def test_query_contract_rejects_invalid_context_and_points():
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"equivalence", "target":{"kind":"equation", "name":"x"}, "comparison":"x"},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"limit", "variable":"x", "point":"0"},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"limit", "variable":"x", "point":"oo", "direction":"left"},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"properties", "checks":[]},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"properties", "checks":[{"kind":"sign", "variable":"x"}]},))
    with pytest.raises(ValidationError): request(queries=({"name":"q", "kind":"properties", "checks":[{"kind":"sign"}, {"kind":"sign"}]},))
    for query in (
        {"name":"oo", "kind":"equivalence", "comparison":"x"},
        {"name":"q", "kind":"properties", "checks":({"kind":"valid_domain", "variable":"oo"},)},
        {"name":"q", "kind":"limit", "variable":"oo", "point":"0", "direction":"both"},
        {"name":"q", "kind":"asymptotic", "variable":"oo", "point":"oo", "order":1},
    ):
        with pytest.raises(ValidationError):
            request(queries=(query,))


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


def test_impossible_denominator_obligations_remain_unresolved():
    for expression, comparison in (
        ("1/0", "1/0"),
        ("0**-1", "0**-1"),
        ("(x-x)/(x-x)", "1"),
    ):
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            queries=({"name":"q", "kind":"equivalence", "comparison":comparison},),
        ))
        assert outcome.status == "success"
        answer = outcome.queries[0].answers[0]
        assert answer.conclusion == "unresolved"
        assert answer.evidence is None
        assert answer.blockers == ("query denominator is identically zero",)


def test_negative_integral_powers_preserve_nonzero_obligations():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x**-1",
        queries=({"name":"q", "kind":"equivalence", "comparison":"x**-1"},),
    ))
    assert outcome.status == "success"
    answer = outcome.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert answer.conditions == ("x != 0",)


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
    assert outcome.queries[1].answers[0].evidence is not None
    assert outcome.queries[2].answers[0].evidence is not None
    assert outcome.queries[2].answers[0].evidence.kind == "asymptotic"
    assert all(answer.derived_candidates == () for result in outcome.queries for answer in result.answers)
    dumped = outcome.model_dump(mode="json")
    assert dumped["queries"][1]["answers"][0]["check"] is None
    assert dumped["queries"][1]["answers"][0]["evidence"]["kind"] == "limit"


def test_asymptotic_rational_local_parameters_orders_and_remainders():
    cases = (
        ("1/(x - 1)", "1", "both", 3, "x - 1", "(1)*t**-1", "O(t**3)"),
        ("(x + 1)/(x - 1)", "oo", None, 3, "1/x", "1 + (2)*t", "O(t**3)"),
        ("1/x**2", "-oo", None, 3, "-1/x", "(1)*t**2", "O(t**3)"),
    )
    for expression, point, direction, order, local, term, big_o in cases:
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression, queries=({
            "name": "a", "kind": "asymptotic", "variable": "x", "point": point,
            "direction": direction, "order": order,
        },)))
        assert outcome.status == "success"
        answer = outcome.queries[0].answers[0]
        assert answer.conclusion == "proved_under_assumptions"
        assert answer.evidence is not None and answer.evidence.kind == "asymptotic"
        assert term in answer.evidence.statement
        assert answer.evidence.remainder is not None
        assert answer.evidence.remainder.local_parameter == local
        assert answer.evidence.remainder.normalized_big_o == big_o


def test_asymptotic_exponential_linear_terms_are_degree_ordered_and_exactly_exhausted():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 3)*2**x",
        queries=({"name": "a", "kind": "asymptotic", "variable": "x", "point": "oo", "order": 2},),
    ))
    assert outcome.status == "success"
    evidence = outcome.queries[0].answers[0].evidence
    assert evidence is not None and evidence.kind == "asymptotic"
    assert evidence.remainder is None
    assert "x + 3" in evidence.statement


def test_asymptotic_intermediate_and_result_rendering_refusals_are_terminal(monkeypatch):
    request_value = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1)/(x - 1)",
        queries=({"name": "a", "kind": "asymptotic", "variable": "x", "point": "oo", "order": 2},),
    )
    monkeypatch.setattr(sympy_backend, "_asymptotic_divide", lambda *_args: None)
    refused = analyze(request_value)
    assert refused.status == "success"
    assert refused.queries[0].answers[0].blockers == ("asymptotic intermediate exceeds its bound",)
    monkeypatch.undo()
    monkeypatch.setattr(sympy_backend, "_asymptotic_render_terms", lambda *_args: "x" * 4097)
    oversized = analyze(request_value)
    assert oversized.status == "success"
    assert oversized.queries[0].answers[0].blockers == ("query result rendering exceeds its bound",)


def test_asymptotic_closed_form_replacement_is_qualified_and_unsupported_is_terminal():
    qualified = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k*q**k, (k, 0, 2))",
        assumptions=(Assumption(name="ratio_not_one", relationship="q < 1"),),
        queries=({"name": "a", "kind": "asymptotic", "variable": "q", "point": "0", "direction": "right", "order": 2},),
    ))
    assert qualified.status == "success"
    answer = qualified.queries[0].answers[0]
    assert answer.conclusion == "proved_under_assumptions"
    assert {use.name for use in answer.assumptions_used} == {"ratio_not_one"}

    for expression, blocker in (
        (
            "sin(x)",
            "asymptotic target is neither a bounded rational expression nor a supported "
            "linear-exponential expression; use a bounded rational or linear-exponential target",
        ),
        (
            "x**9",
            "asymptotic rational target exceeds bounded rational degree limit: observed 9, "
            "configured 8; use a smaller bounded rational target",
        ),
    ):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression, queries=({"name": "a", "kind": "asymptotic", "variable": "x", "point": "oo", "order": 1},)))
        assert outcome.status == "success"
        assert outcome.queries[0].answers[0].conclusion == "unresolved"
        assert outcome.queries[0].answers[0].blockers == (blocker,)


def test_counterexample_model_rejects_noncanonical_values():
    for target_value, comparison_value in (("zoo", "0"), ("nan", "0"), ("2/4", "0")):
        with pytest.raises(ValidationError):
            CounterexampleEvidence(
                substitutions={"x": "1"},
                target_value=target_value,
                comparison_value=comparison_value,
            )


def test_result_models_reject_wrong_evidence_and_answer_cardinality():
    interpretation = Interpretation(normalized_sympy="x", normalized_latex="x")
    answer = QueryAnswer(conclusion="proved", evidence=IdentityEvidence(statement="same"))
    EquivalenceResult(name="q", target={"kind":"expression"}, normalized_target=interpretation, summary="same", answers=(answer,))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="q", target={"kind":"expression"}, normalized_target=interpretation, summary="same", answers=(answer, answer))
    with pytest.raises(ValidationError):
        QueryAnswer(conclusion="unresolved", blockers=("unsupported",), derived_candidates=({"interpretation": interpretation, "operation_counts": OperationCounts()},))


def test_provenance_population_refusal_does_not_escape_analyze():
    terms = ["x", *(f"y{index}" for index in range(128))]
    while len(terms) > 1:
        terms = [
            f"({terms[index]} + {terms[index + 1]})"
            if index + 1 < len(terms)
            else terms[index]
            for index in range(0, len(terms), 2)
        ]
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=terms[0],
        variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        definitions=(DirectedDefinition(variable="x", expression="1"),),
        assumptions=tuple(
            Assumption(name=f"a{index}", relationship=f"y{index} == x")
            for index in range(128)
        ),
        queries=({"name":"q", "kind":"equivalence", "comparison":"129"},),
    ))
    assert outcome.status == "success"
    assert outcome.queries[0].answers[0].conclusion == "unresolved"
    assert outcome.queries[0].answers[0].blockers == (
        "query assumption provenance exceeds its bound",
    )


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


def test_query_preflight_rejects_before_denominator_rendering(monkeypatch):
    expression = parse_expression("1/(x**9)")
    assert not isinstance(expression, tuple)
    target = QueryTarget(
        target={"kind": "expression"},
        expression=expression,  # pyright: ignore[reportArgumentType]
        interpretation=Interpretation(normalized_sympy="x**(-9)", normalized_latex="x^{-9}"),
    )
    called = False

    def forbidden(_value):
        nonlocal called
        called = True
        raise AssertionError("denominator rendering must remain behind whole-query preflight")

    monkeypatch.setattr(formula_query, "render", forbidden)
    result = formula_query.evaluate_queries(
        (EquivalenceQuery(name="q", comparison="0"),),
        target,
        ReasoningContext.build({}, (), ()),
    )
    assert isinstance(result, tuple)
    assert result[0].answers[0].conclusion == "unresolved"
    assert not called


def test_expanded_term_growth_is_rejected_before_backend_calls(monkeypatch):
    parsed = parse_expression(f"({' + '.join('abcdefghij')})**8")
    assert not isinstance(parsed, tuple)
    called = False

    def forbidden(_value):
        nonlocal called
        called = True
        raise AssertionError("term-growth preflight must precede backend conversion")

    monkeypatch.setattr(formula_sympy, "_to_sympy", forbidden)
    assert formula_sympy.bounded_rational_difference(parsed, IntegerLiteral(0)) is None  # pyright: ignore[reportArgumentType]
    assert not called


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
    for comparison, blocker in (
        (
            "x**9",
            "equivalence operand exceeds bounded rational degree limit: observed 9, "
            "configured 8; use bounded rational operands",
        ),
        (
            "x**33",
            "equivalence operand exceeds bounded rational exponent limit: observed 33, "
            "configured 32; use bounded rational operands",
        ),
        (
            f"{1 << 1024}*x",
            "equivalence operand exceeds bounded rational coefficient-bit limit: observed 1025, "
            "configured 1024; use bounded rational operands",
        ),
        (
            f"{1 << 600}*{1 << 423}",
            "equivalence operand exceeds bounded rational coefficient-bit limit; "
            "use bounded rational operands",
        ),
        (
            "(x/x)**9",
            "equivalence operand exceeds bounded rational degree limit; "
            "use bounded rational operands",
        ),
    ):
        outcome = analyze(request(queries=({"name":"q", "kind":"equivalence", "comparison":comparison},)))
        assert outcome.status == "success"
        answer = outcome.queries[0].answers[0]
        assert answer.conclusion == "unresolved"
        assert answer.blockers == (blocker,)

    expanded = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="y",
            variables={
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "y": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
            definitions=(DirectedDefinition(variable="y", expression="x**9"),),
            queries=({"name": "q", "kind": "equivalence", "comparison": "y"},),
        )
    )
    assert expanded.status == "success"
    assert expanded.queries[0].answers[0].blockers == (
        "equivalence expansion exceeds bounded rational degree limit: observed 9, configured 8; "
        "use bounded rational operands",
    )

    nonlinear = analyze(request(
        assumptions=(Assumption(name="nonlinear", relationship="(x + 1)**8 > 0"),),
        queries=({"name":"q", "kind":"equivalence", "comparison":"x"},),
    ))
    assert nonlinear.status == "success"
    answer = nonlinear.queries[0].answers[0]
    assert answer.conclusion == "proved"
    assert answer.relevant_unsupported_assumptions == ("nonlinear",)


def test_rational_measure_failures_are_closed_and_report_first_bounded_fact():
    cases = (
        ("sin(x)", "unsupported_form", None, None),
        ("x**33", "exponent", 33, 32),
        ("x**9", "degree", 9, 8),
        (f"{1 << 1024}", "coefficient_bits", 1025, 1024),
        (f"({' + '.join('abcdefghij')})**8", "expanded_terms", None, 4096),
        ("((x + 1) - (x + 1))**9", "degree", None, 8),
        ("(x/x)**9", "degree", None, 8),
        (f"{1 << 600}*{1 << 423}", "coefficient_bits", None, 1024),
    )
    for source, kind, observed, configured in cases:
        parsed = parse_expression(source)
        assert not isinstance(parsed, tuple)
        failure = formula_sympy.rational_ir_measure(parsed)  # pyright: ignore[reportArgumentType]
        assert isinstance(failure, formula_sympy.RationalMeasureFailure)
        assert (failure.kind, failure.observed, failure.configured) == (
            kind,
            observed,
            configured,
        )

    nodes = parse_expression("x + y")
    assert not isinstance(nodes, tuple)
    node_failure = formula_sympy.rational_ir_measure(nodes, max_nodes=2)  # pyright: ignore[reportArgumentType]
    assert isinstance(node_failure, formula_sympy.RationalMeasureFailure)
    assert (node_failure.kind, node_failure.observed, node_failure.configured) == (
        "nodes",
        3,
        2,
    )


def test_equivalence_reports_operand_expansion_and_normalization_refusals(monkeypatch):
    operand = analyze(request(queries=({"name": "q", "kind": "equivalence", "comparison": "sin(x)"},)))
    assert operand.status == "success"
    operand_answer = operand.queries[0].answers[0]
    assert operand_answer.conclusion == "unresolved"
    assert operand_answer.blockers == (
        "equivalence operand is outside the bounded rational family; use bounded rational operands",
    )

    expanded = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="y",
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            "y": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        definitions=(DirectedDefinition(variable="y", expression="sin(x)"),),
        queries=({"name": "q", "kind": "equivalence", "comparison": "y"},),
    ))
    assert expanded.status == "success"
    expanded_answer = expanded.queries[0].answers[0]
    assert expanded_answer.conclusion == "unresolved"
    assert expanded_answer.blockers == (
        "equivalence expansion is outside the bounded rational family; use bounded rational operands",
    )

    monkeypatch.setattr(formula_query, "bounded_rational_difference", lambda *_args: None)
    normalization = analyze(request(queries=({"name": "q", "kind": "equivalence", "comparison": "x"},)))
    assert normalization.status == "success"
    normalization_answer = normalization.queries[0].answers[0]
    assert normalization_answer.conclusion == "unresolved"
    assert normalization_answer.blockers == ("query rational normalization exceeds its bound",)


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
