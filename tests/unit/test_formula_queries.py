# ruff: noqa: E501, E701
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import py_science.formula.equivalence as formula_equivalence
import py_science.formula.query as formula_query
import py_science.formula.series as formula_series
import py_science.formula.service as formula_query_service
import py_science.formula.sympy_backend as formula_sympy
import py_science.formula.sympy_backend as sympy_backend
import pytest
from py_science.formula import (
    AnalysisRequest,
    Assumption,
    ClosedFormResult,
    CounterexampleEvidence,
    DerivedTarget,
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


def test_lexical_binding_equivalence_uses_represented_value() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Let(t, x + 1, t*t)",
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            queries=(
                {"name": "q", "kind": "equivalence", "comparison": "(x + 1)**2"},
            ),
        )
    )

    assert outcome.status == "success"
    assert outcome.interpretation.normalized_sympy == "Let(t, x + 1, t*t)"
    assert outcome.queries[0].answers[0].conclusion == "proved"


@pytest.mark.parametrize(
    ("analysis_request", "submitted_source"),
    (
        (
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="x + 1",
                queries=(
                    {"name": "q", "kind": "equivalence", "comparison": "1 + x"},
                ),
            ),
            "x + 1",
        ),
        (
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                equations=(EquationRequest(name="value", expression="Eq(y, x + 1)"),),
                variables={
                    "x": VariableDeclaration(domain=MathematicalDomain.REAL)
                },
                queries=(
                    {
                        "name": "q",
                        "kind": "equivalence",
                        "target": {"kind": "equation", "name": "value"},
                        "comparison": "1 + x",
                    },
                ),
            ),
            "Eq(y, x + 1)",
        ),
    ),
)
def test_query_targets_reuse_retained_parsed_operands(
    monkeypatch, analysis_request, submitted_source
):
    parsed_sources = []
    original_parse = formula_query_service.parse_expression

    def tracked_parse(source):
        parsed_sources.append(source)
        return original_parse(source)

    monkeypatch.setattr(formula_query_service, "parse_expression", tracked_parse)
    outcome = analyze(analysis_request)

    assert outcome.status == "success"
    assert parsed_sources == [submitted_source]


def test_retained_analysis_state_is_deeply_read_only(monkeypatch):
    retained = []
    original_attach = formula_query_service._attach_queries

    def capture(request, analyzed):
        retained.append(analyzed)
        return original_attach(request, analyzed)

    monkeypatch.setattr(formula_query_service, "_attach_queries", capture)
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(EquationRequest(name="value", expression="Eq(y[i], x[i])", domains={"i": {"lower": "0", "upper": "n"}}),),
            variables={
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "n": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            },
            queries=(
                {
                    "name": "q",
                    "kind": "equivalence",
                    "target": {"kind": "equation", "name": "value"},
                    "comparison": "x[i]",
                },
            ),
        )
    )

    assert outcome.status == "success"
    analyzed = retained[0]
    with pytest.raises(TypeError):
        analyzed.equation_analyses["other"] = analyzed.aggregate_analysis
    with pytest.raises(TypeError):
        analyzed.equations[0].domains["j"] = analyzed.equations[0].domains["i"]
    assert not hasattr(analyzed.equations[0], "request")
    with pytest.raises(FrozenInstanceError):
        analyzed.equations[0].name = "other"
    with pytest.raises(FrozenInstanceError):
        analyzed.aggregate_analysis.opaque_work = IntegerLiteral(1)


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

    for expression, conclusion, blocker in (("Sum(k * 2**k, (k, 0, oo))", "inapplicable", None), ("Sum(k * q**k, (k, 0, oo))", "unresolved", "series convergence is not proved"), ("Sum(Sum(k * q**k, (k, 0, 1)), (j, 0, 1))", "unresolved", "nested polynomial summand contains forbidden or undeclared names"), ("Sum(k**2 * q**k, (k, 0, 1))", "unresolved", "closed-form summand does not match (a*k+b)*r**k; use a summand in that form")):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression, queries=({"name": "series", "kind": "closed_form"},)))
        assert outcome.status == "success"
        terminal = outcome.queries[0].answers[0]
        assert terminal.conclusion == conclusion
        if blocker is not None: assert terminal.blockers == (blocker,)
    empty = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(k * q**k, (k, 2, 1))", queries=({"name": "empty", "kind": "closed_form"},)))
    assert empty.status == "success"
    assert empty.queries[0].answers[0].conclusion == "proved_under_assumptions"
    assert empty.queries[0].answers[0].derived_candidates[0].interpretation.normalized_sympy == "0"


def test_nested_finite_polynomial_closed_form_is_direct_only():
    nested = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(Sum(1, (l, -k, k)), (k, 0, p))", variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}, queries=({"name": "closed", "kind": "closed_form"},)))
    assert nested.status == "success"
    answer = nested.queries[0].answers[0]
    assert answer.conclusion == "proved"
    assert answer.evidence is not None and answer.evidence.kind == "closed_form"
    assert answer.derived_candidates[0].interpretation.normalized_sympy == "(p + 1)**2"
    direct_property = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(Sum(1, (l, -k, k)), (k, 0, p))", variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}, queries=({"name": "properties", "kind": "properties", "checks": ({"kind": "sign"},)},)))
    assert direct_property.status == "success"
    assert direct_property.queries[0].answers[0].conclusion == "unresolved"


def _nested_answer(expression, **extra):
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=expression,
        queries=({"name": "nested", "kind": "closed_form"},),
        **extra,
    ))
    assert outcome.status == "success"
    return outcome.queries[0].answers[0]


def test_nested_polynomial_shell_topology_and_resource_boundaries():
    variables = {"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}
    shell = _nested_answer(
        "3 + 2*Sum(Sum(1, (l, -k, k)), (k, 0, p))", variables=variables
    )
    assert shell.conclusion == "proved"
    actual = formula_sympy.sympy.sympify(
        shell.derived_candidates[0].interpretation.normalized_sympy
    )
    expected = formula_sympy.sympy.sympify("2*p**2 + 4*p + 5")
    assert formula_sympy.sympy.expand(actual).equals(formula_sympy.sympy.expand(expected))

    branching = _nested_answer(
        "Sum(Sum(Sum(1, (a, 0, 1)) + Sum(1, (b, 0, 1)), (c, 0, 1)) + "
        "Sum(Sum(Sum(1, (d, 0, 1)), (e, 0, 1)) + Sum(1, (f, 0, 1)), (g, 0, 1)), "
        "(h, 0, 1))"
    )
    assert branching.conclusion == "proved"  # eight nodes, depth four
    per_binder = _nested_answer(
        "Sum(Sum(k**8*l**8, (l, 0, 1)), (k, 0, 1))"
    )
    assert per_binder.conclusion == "proved"

    introduced_depth = _nested_answer(
        "Sum(Sum(x, (l, 0, 1)), (k, 0, 1))",
        variables={"x": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        definitions=(
            DirectedDefinition(
                variable="x",
                expression="Sum(Sum(Sum(1, (a, 0, 1)), (b, 0, 1)), (c, 0, 1))",
            ),
        ),
    )
    assert introduced_depth.conclusion == "unresolved"
    assert "depth four and eight sums" in introduced_depth.blockers[0]
    introduced_count = _nested_answer(
        "Sum(Sum(x, (l, 0, 1)), (k, 0, 1))",
        variables={"x": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        definitions=(
            DirectedDefinition(
                variable="x",
                expression=" + ".join(
                    f"Sum(1, (i{index}, 0, 1))" for index in range(7)
                ),
            ),
        ),
    )
    assert introduced_count.conclusion == "unresolved"
    assert "depth four and eight sums" in introduced_count.blockers[0]

    for expression, blocker in (
        ("Sum(Sum(Sum(Sum(Sum(1, (a, 0, 1)), (b, 0, 1)), (c, 0, 1)), (d, 0, 1)), (e, 0, 1))", "one tree of at most depth four and eight sums"),
        ("Sum(Sum(Sum(1, (a, 0, 1)) + Sum(1, (b, 0, 1)), (c, 0, 1)) + Sum(Sum(1, (d, 0, 1)) + Sum(1, (e, 0, 1)) + Sum(1, (f, 0, 1)) + Sum(1, (g, 0, 1)), (h, 0, 1)), (i, 0, 1))", "one tree of at most depth four and eight sums"),
        ("Sum(Sum(1, (l, 0, k)), (k, 0, 1)) + Sum(Sum(1, (j, 0, i)), (i, 0, 1))", "one tree of at most depth four and eight sums"),
        ("Sum(Sum(2**l, (l, 0, k)), (k, 0, 1))", "exact rational polynomial"),
        ("Sum(Sum(1, (l, 0, oo)), (k, 0, 1))", "finite and independent"),
    ):
        answer = _nested_answer(expression)
        assert answer.conclusion == "unresolved"
        assert blocker in answer.blockers[0]


def test_nested_polynomial_affine_integral_order_and_degree_contract():
    integer = {"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}
    accepted = _nested_answer(
        "Sum(Sum(p + l**8, (l, 0, 1)), (k, 0, 1))", variables=integer
    )
    assert accepted.conclusion == "proved"
    dependent = _nested_answer(
        "Sum(Sum(1, (l, k, p)), (k, 0, p))", variables=integer
    )
    assert dependent.conclusion == "proved"

    for expression, blocker, extra in (
        ("Sum(Sum(1, (l, k**2, k**2)), (k, 0, p))", "affine integers", {"variables": integer}),
        ("Sum(Sum(1, (l, k/2, k/2)), (k, 0, p))", "affine integers", {"variables": integer}),
        ("Sum(Sum(1/(k + 1), (l, 0, 1)), (k, 0, p))", "exact rational polynomial", {"variables": integer}),
        ("Sum(Sum(k**9, (l, 0, 1)), (k, 0, p))", "degree at most eight", {"variables": integer}),
        ("Sum(Sum(y, (l, 0, 1)), (k, 0, p))", "capture a bound", {"variables": {**integer, "k": VariableDeclaration(domain=MathematicalDomain.INTEGER), "y": VariableDeclaration(domain=MathematicalDomain.INTEGER)}, "definitions": (DirectedDefinition(variable="y", expression="k**9"),)}),
        ("Sum(Sum(k**8, (l, 0, k)), (k, 0, p))", "degree at most eight", {"variables": integer}),
    ):
        answer = _nested_answer(expression, **extra)
        assert answer.conclusion == "unresolved"
        assert blocker in answer.blockers[0]

    empty = _nested_answer("Sum(Sum(1, (l, 2, 1)), (k, 0, 1))")
    assert empty.derived_candidates[0].interpretation.normalized_sympy == "0"
    for excluded in (
        "Sum(Sum(1, (l, 0, oo)), (k, 1, 0))",
        "Sum(Sum(2**l, (l, 0, 1)), (k, 1, 0))",
        "Sum(Sum(1, (l, k**2, k**2)), (k, 1, 0))",
        "Sum(Sum(1, (l, l, 1)), (k, 1, 0))",
    ):
        excluded_answer = _nested_answer(excluded)
        assert excluded_answer.conclusion == "unresolved"
        assert not excluded_answer.derived_candidates
    changing = _nested_answer("Sum(Sum(1, (l, -k, k)), (k, -1, 1))")
    assert changing.conclusion == "unresolved"
    assert changing.blockers == ("nested polynomial range ordering is unresolved",)


def test_nested_polynomial_backend_generation_is_never_proof(monkeypatch):
    expression = "Sum(Sum(1, (l, 0, k)), (k, 0, 2))"
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_candidate", lambda *args: None)
    missing = _nested_answer(expression)
    assert missing.conclusion == "unresolved" and missing.evidence is None
    assert missing.blockers == ("nested polynomial antidifference verification failed",)

    monkeypatch.undo()
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_verify", lambda *args: False)
    answer = _nested_answer(expression)
    assert answer.conclusion == "unresolved" and answer.evidence is None
    assert answer.blockers == ("nested polynomial antidifference verification failed",)

    monkeypatch.undo()
    monkeypatch.setattr(
        formula_series,
        "bounded_polynomial_sum_candidate",
        lambda *args: formula_sympy.sympy.Symbol("_nested_escape"),
    )
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_verify", lambda *args: True)
    escaped = _nested_answer(expression)
    assert escaped.conclusion == "unresolved" and escaped.evidence is None
    assert escaped.blockers == ("nested polynomial candidate escapes its restricted names or bounds",)

    monkeypatch.undo()
    monkeypatch.setattr(
        formula_series,
        "bounded_polynomial_sum_candidate",
        lambda *args: formula_sympy.sympy.Function("unsupported")(formula_sympy.sympy.Symbol("k")),
    )
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_verify", lambda *args: True)
    unparsable = _nested_answer(expression)
    assert unparsable.conclusion == "unresolved" and unparsable.evidence is None

    monkeypatch.undo()
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_verify", lambda *args: True)
    monkeypatch.setattr(
        formula_series,
        "bounded_polynomial_sum_candidate",
        lambda *args: formula_sympy.sympy.Integer(0),
    )
    zero = _nested_answer(expression)
    assert zero.conclusion == "proved"
    assert zero.derived_candidates[0].interpretation.normalized_sympy == "0"

    monkeypatch.undo()
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_verify", lambda *args: True)

    def negative_candidate(_body, index, *_bounds):
        return -formula_sympy.sympy.Symbol("k") if index == "l" else formula_sympy.sympy.Integer(-1)

    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_candidate", negative_candidate)
    negative = _nested_answer(expression)
    assert negative.conclusion == "proved"
    assert negative.derived_candidates[0].interpretation.normalized_sympy == "-1"


def test_nested_polynomial_candidate_and_rendering_overflow_fail_closed(monkeypatch):
    target_terms = ["x"] * 257
    while len(target_terms) > 1:
        target_terms = [
            f"({target_terms[index]} + {target_terms[index + 1]})"
            if index + 1 < len(target_terms)
            else target_terms[index]
            for index in range(0, len(target_terms), 2)
        ]
    oversized_target = _nested_answer(
        f"Sum(Sum({target_terms[0]}, (l, 0, 1)), (k, 0, 1))"
    )
    assert oversized_target.conclusion == "unresolved"
    assert "closed-form target exceeds its bounded node limit" in oversized_target.blockers[0]

    expression = "Sum(Sum(1, (l, 0, k)), (k, 0, 2))"
    huge = formula_sympy.sympy.Add(
        *(formula_sympy.sympy.Symbol(f"x{index}") for index in range(4100)),
        evaluate=False,
    )
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_candidate", lambda *args: huge)
    monkeypatch.setattr(formula_series, "bounded_polynomial_sum_verify", lambda *args: True)
    bounded = _nested_answer(expression)
    assert bounded.conclusion == "unresolved" and bounded.evidence is None

    monkeypatch.undo()
    original_render = formula_series.render

    def oversized_render(value):
        rendered = original_render(value)
        if not isinstance(value, formula_series.Sum):
            return rendered.__class__("x" * 4097, "x" * 4097)
        return rendered

    monkeypatch.setattr(formula_series, "render", oversized_render)
    oversized = _nested_answer(expression)
    assert oversized.conclusion == "unresolved"
    assert oversized.blockers == ("query candidate rendering exceeds its bound",)


def test_nested_polynomial_backend_independently_checks_step_boundary_and_bounds(monkeypatch):
    body = parse_expression("k")
    lower = parse_expression("0")
    upper = parse_expression("3")
    assert not isinstance(body, tuple) and not isinstance(lower, tuple) and not isinstance(upper, tuple)
    candidate = formula_sympy.bounded_polynomial_sum_candidate(body, "k", lower, upper)
    assert candidate is not None
    assert formula_sympy.bounded_polynomial_sum_verify(body, "k", lower, upper, candidate)
    assert not formula_sympy.bounded_polynomial_sum_verify(body, "k", lower, upper, candidate + 1)

    monkeypatch.setattr(formula_sympy.sympy, "summation", lambda *args: formula_sympy.sympy.Integer(0))
    assert not formula_sympy.bounded_polynomial_sum_verify(body, "k", lower, upper, candidate)
    monkeypatch.undo()
    original_bound = formula_sympy._series_value_is_bounded
    for rejected_call in range(1, 9):
        calls = 0

        def reject_intermediate(value, rejected=rejected_call, **kwargs):
            nonlocal calls
            calls += 1
            return False if calls == rejected else original_bound(value, **kwargs)

        monkeypatch.setattr(formula_sympy, "_series_value_is_bounded", reject_intermediate)
        assert not formula_sympy.bounded_polynomial_sum_verify(body, "k", lower, upper, candidate)
        monkeypatch.undo()


def test_nested_polynomial_binders_shadow_declared_definitions():
    unused_shadow = _nested_answer(
        "Sum(Sum(k, (k, 0, 1)), (j, 0, 1))",
        variables={"k": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        definitions=(DirectedDefinition(variable="k", expression="100"),),
    )
    assert unused_shadow.conclusion == "proved"
    assert unused_shadow.assumptions_used == ()

    answer = _nested_answer(
        "Sum(Sum(1, (l, -k, k)), (k, 0, 1))",
        variables={"k": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        definitions=(DirectedDefinition(variable="k", expression="100"),),
    )
    assert answer.conclusion == "proved"
    assert answer.derived_candidates[0].interpretation.normalized_sympy == "4"
    assert answer.assumptions_used == ()

    captured = _nested_answer(
        "Sum(Sum(x, (l, 0, 1)), (k, 0, 1))",
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.INTEGER),
            "k": VariableDeclaration(domain=MathematicalDomain.INTEGER),
        },
        definitions=(DirectedDefinition(variable="x", expression="k"),),
    )
    assert captured.conclusion == "unresolved"
    assert captured.blockers == (
        "nested polynomial reasoning would capture a bound name",
    )
    assert not captured.derived_candidates

    transitive = _nested_answer(
        "Sum(Sum(x, (l, 0, 1)), (k, 0, 1))",
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.INTEGER),
            "y": VariableDeclaration(domain=MathematicalDomain.INTEGER),
            "k": VariableDeclaration(domain=MathematicalDomain.INTEGER),
        },
        definitions=(
            DirectedDefinition(variable="x", expression="y"),
            DirectedDefinition(variable="y", expression="k"),
        ),
    )
    assert transitive.conclusion == "unresolved"
    assert transitive.blockers == (
        "nested polynomial reasoning would capture a bound name",
    )
    assert not transitive.derived_candidates

    safe_sibling = _nested_answer(
        "Sum(Sum(x, (l, 0, 1)), (k, 0, 1))",
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.INTEGER),
            "y": VariableDeclaration(domain=MathematicalDomain.INTEGER),
            "j": VariableDeclaration(domain=MathematicalDomain.INTEGER),
        },
        definitions=(
            DirectedDefinition(variable="x", expression="Sum(1, (j, 0, 1)) + y"),
            DirectedDefinition(variable="y", expression="j"),
        ),
    )
    assert safe_sibling.conclusion == "proved_under_assumptions"
    assert safe_sibling.derived_candidates

    free_limit = _nested_answer(
        "Sum(Sum(1, (l, l, 1)), (k, 0, 1))",
        variables={"l": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        definitions=(DirectedDefinition(variable="l", expression="0"),),
    )
    assert free_limit.conclusion == "proved_under_assumptions"
    assert free_limit.derived_candidates[0].interpretation.normalized_sympy == "4"

    empty_from_definition = _nested_answer(
        "Sum(Sum(1, (l, 0, 1)), (k, lower, 0))",
        variables={"lower": VariableDeclaration(domain=MathematicalDomain.INTEGER)},
        definitions=(DirectedDefinition(variable="lower", expression="1"),),
    )
    assert empty_from_definition.conclusion == "proved_under_assumptions"
    assert empty_from_definition.derived_candidates[0].interpretation.normalized_sympy == "0"
    assert tuple(use.name for use in empty_from_definition.assumptions_used) == ("lower",)


def test_nested_reasoning_expansion_has_a_shared_budget(monkeypatch):
    target_terms = ["x"] * 100
    while len(target_terms) > 1:
        target_terms = [
            f"({target_terms[index]} + {target_terms[index + 1]})"
            if index + 1 < len(target_terms)
            else target_terms[index]
            for index in range(0, len(target_terms), 2)
        ]
    replacement = " + ".join("y" for _ in range(50))
    expression = parse_expression(
        f"Sum(Sum({target_terms[0]}, (l, 0, 1)), (k, 0, 1))"
    )
    replacement_expression = parse_expression(replacement)
    assert not isinstance(expression, tuple) and not isinstance(replacement_expression, tuple)
    reasoning = ReasoningContext.build(
        {"x": MathematicalDomain.INTEGER, "y": MathematicalDomain.INTEGER},
        (
            SimpleNamespace(
                name="x", expression=replacement_expression, source=f"x = {replacement}"
            ),
        ),
        (),
    )
    bounded = formula_series.derive_closed_form(expression, reasoning)
    assert bounded.conclusion == "unresolved"
    assert bounded.blockers == ("query reasoning exceeds its bound",)

    monkeypatch.setattr(formula_series, "MAX_INTERMEDIATE_NODES", 20_000)
    falsified = formula_series.derive_closed_form(expression, reasoning)
    assert falsified.conclusion == "unresolved"
    assert falsified.blockers == (
        "nested polynomial family exceeds its bounded preconditions",
    )


def test_nested_polynomial_direct_consumers_and_explicit_derived_reuse():
    expression = "Sum(Sum(1, (l, -k, k)), (k, 0, p))"
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=expression,
        variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)},
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {"name": "equivalent", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "(p + 1)**2"},
            {"name": "properties", "kind": "properties", "target": {"kind": "derived", "query": "closed"}, "checks": ({"kind": "sign"},)},
            {"name": "limit", "kind": "limit", "target": {"kind": "derived", "query": "closed"}, "variable": "p", "point": "oo"},
            {"name": "asymptotic", "kind": "asymptotic", "target": {"kind": "derived", "query": "closed"}, "variable": "p", "point": "oo", "order": 2},
        ),
    ))
    assert outcome.status == "success"
    assert [item.answers[0].conclusion for item in outcome.queries] == [
        "proved", "proved", "proved", "proved", "proved_under_assumptions"
    ]
    assert all(isinstance(item.target, DerivedTarget) for item in outcome.queries[1:])
    assert outcome.queries[2].answers[0].evidence is not None
    assert outcome.queries[2].answers[0].evidence.kind == "property"
    assert outcome.queries[4].answers[0].evidence is not None
    assert outcome.queries[4].answers[0].evidence.kind == "asymptotic"

    for query in (
        {"name": "properties", "kind": "properties", "checks": ({"kind": "sign"},)},
        {"name": "limit", "kind": "limit", "variable": "p", "point": "oo"},
        {"name": "asymptotic", "kind": "asymptotic", "variable": "p", "point": "oo", "order": 2},
    ):
        direct = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)},
            queries=(query,),
        ))
        assert direct.status == "success"
        assert direct.queries[0].answers[0].conclusion == "unresolved"
        assert direct.queries[0].answers[0].blockers


def test_nested_polynomial_canonicalizes_packed_and_literal_m2l_counts():
    variables = {"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}
    cases = (
        (
            "Sum(Sum(Sum(2*k + 1, (k, 0, p-n)), (m, 0, n)), (n, 0, p))",
            "(p + 1)*(p + 2)**2*(p + 3)/12",
            "(p + 1)*(p + 3)*(p + 2)**2/12",
            "3185",
            True,
        ),
        (
            "Sum(Sum(Sum(2*k + 1, (k, 0, p-n)), (m, -n, n)), (n, 0, p))",
            "(p + 1)*(p + 2)*(p**2 + 3*p + 3)/6",
            "(p + 1)*(p + 2)*(3*p + 3 + p**2)/6",
            "5551",
            False,
        ),
    )
    for expression, comparison, canonical, fixed_value, check_sign in cases:
        queries = [
            {"name": "closed", "kind": "closed_form"},
            {"name": "compact", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": comparison},
            {"name": "asymptotic", "kind": "asymptotic", "target": {"kind": "derived", "query": "closed"}, "variable": "p", "point": "oo", "order": 2},
        ]
        if check_sign:
            queries.append({"name": "sign", "kind": "properties", "target": {"kind": "derived", "query": "closed"}, "checks": ({"kind": "sign"},)})
        general = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            variables=variables,
            queries=tuple(queries),  # pyright: ignore[reportArgumentType]
        ))
        assert general.status == "success"
        assert general.queries[0].answers[0].derived_candidates[0].interpretation.normalized_sympy == canonical
        assert all(item.answers[0].conclusion in {"proved", "proved_under_assumptions"} for item in general.queries)
        submitted = parse_expression(expression)
        assert not isinstance(submitted, tuple)
        assert general.queries[0].answers[0].evidence.statement.startswith(  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
            f"{formula_sympy.render(submitted).sympy} = "
        )

        fixed = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            variables=variables,
            assumptions=(Assumption(name="fixed_order", relationship="p == 12"),),
            queries=(
                {"name": "closed", "kind": "closed_form"},
                {"name": "value", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": fixed_value},
            ),
        ))
        assert fixed.status == "success"
        assert fixed.queries[1].answers[0].conclusion == "proved_under_assumptions"
        assert {item.name for item in fixed.queries[1].answers[0].assumptions_used} == {"fixed_order"}


@pytest.mark.parametrize(
    ("attribute", "replacement"),
    (
        ("bounded_polynomial_canonical_candidate", lambda *args: None),
        ("bounded_polynomial_canonical_verify", lambda *args: False),
    ),
)
def test_nested_polynomial_canonicalization_fails_closed(
    monkeypatch, attribute, replacement
):
    monkeypatch.setattr(formula_series, attribute, replacement)
    answer = _nested_answer(
        "Sum(Sum(1, (l, -k, k)), (k, 0, p))",
        variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)},
    )
    assert answer.conclusion == "unresolved"
    assert answer.derived_candidates == ()
    assert answer.blockers == ("nested polynomial canonicalization failed",)


def test_nested_polynomial_canonicalization_preserves_a_qualified_rational_shell():
    expression = "Sum(Sum(1, (l, -k, k)), (k, 0, p))/q"
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=expression,
        variables={
            "p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "q": VariableDeclaration(domain=MathematicalDomain.POSITIVE_REAL),
        },
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {
                "name": "same",
                "kind": "equivalence",
                "target": {"kind": "derived", "query": "closed"},
                "comparison": "(p + 1)**2/q",
            },
        ),
    ))
    assert outcome.status == "success"
    assert outcome.queries[0].answers[0].conclusion == "proved_under_assumptions"
    assert outcome.queries[0].answers[0].conditions == ("q != 0",)
    assert outcome.queries[1].answers[0].conclusion == "proved_under_assumptions"


def test_real_nested_polynomial_canonical_verifier_rejects_wrong_candidate():
    expression = parse_expression("p**2 + 2*p + 1")
    assert not isinstance(expression, tuple)
    assert not formula_sympy.bounded_polynomial_canonical_verify(
        expression, formula_sympy.sympy.Integer(0)  # pyright: ignore[reportArgumentType]
    )


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

    monkeypatch.setattr(formula_equivalence, "render", forbidden)
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

    monkeypatch.setattr(formula_equivalence, "bounded_rational_difference", lambda *_args: None)
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


def test_derived_target_reuses_earlier_verified_candidate():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k * 2**k, (k, 0, 3))",
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {"name": "same", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "34"},
        ),
    ))
    assert outcome.status == "success"
    assert outcome.queries[1].target.kind == "derived"
    assert outcome.queries[1].normalized_target is not None
    assert outcome.queries[1].answers[0].conclusion == "proved_under_assumptions"


def test_derived_properties_inherit_source_qualification_for_every_check():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k*q**k, (k, 0, 2))",
        assumptions=(Assumption(name="q_lt_one", relationship="q < 1"),),
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {
                "name": "properties",
                "kind": "properties",
                "target": {"kind": "derived", "query": "closed"},
                "checks": (
                    {"kind": "valid_domain", "variable": "q"},
                    {"kind": "singularities", "variable": "q"},
                ),
            },
        ),
    ))
    assert outcome.status == "success"
    result = outcome.queries[1]
    assert isinstance(result.target, DerivedTarget)
    assert result.normalized_target is not None
    assert len(result.answers) == 2
    for answer in result.answers:
        assert answer.conclusion == "proved_under_assumptions"
        assert "q != 1" in answer.conditions
        assert tuple(use.name for use in answer.assumptions_used) == ("q_lt_one",)


def test_unavailable_derived_properties_preserve_all_correlated_answers():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k*q**k, (k, 0, oo))",
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {
                "name": "properties",
                "kind": "properties",
                "target": {"kind": "derived", "query": "closed"},
                "checks": (
                    {"kind": "valid_domain", "variable": "q"},
                    {"kind": "singularities", "variable": "q"},
                ),
            },
        ),
    ))
    assert outcome.status == "success"
    result = outcome.queries[1]
    assert result.normalized_target is None
    assert len(result.answers) == 2
    assert all(answer.conclusion == "inapplicable" for answer in result.answers)
    assert all(
        answer.blockers == ("derived target source closed concluded unresolved",)
        for answer in result.answers
    )


def test_derived_target_uses_its_non_adjacent_named_source_qualification():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(k*q**k, (k, 0, 2))",
        assumptions=(Assumption(name="q_lt_one", relationship="q < 1"),),
        queries=(
            {"name": "closed", "kind": "closed_form"},
            {"name": "middle", "kind": "equivalence", "comparison": "Sum(k*q**k, (k, 0, 2))"},
            {"name": "dependent", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "q + 2*q**2"},
        ),
    ))
    assert outcome.status == "success"
    answer = outcome.queries[2].answers[0]
    assert answer.conditions == ("q != 1",)
    assert tuple(use.name for use in answer.assumptions_used) == ("q_lt_one",)


def test_derived_results_inherit_the_named_source_qualification_and_preserve_terminal_details():
    interpretation = Interpretation(normalized_sympy="34", normalized_latex="34")
    source = ClosedFormResult(
        name="closed", target={"kind": "expression"}, normalized_target=interpretation,
        summary="closed", answers=(QueryAnswer(
            conclusion="unresolved", conditions=("source condition",),
            assumptions_used=({"name": "source", "relationship": "q < 1"},),
            relevant_unsupported_assumptions=("source unsupported",), blockers=("source blocker",),
        ),),
    )
    dependent = EquivalenceResult(
        name="dependent", target=DerivedTarget(query="closed"), normalized_target=None,
        summary="unavailable", answers=(QueryAnswer(
            conclusion="inapplicable", blockers=("derived target source closed concluded unresolved",),
        ),),
    )
    composed = formula_query_service._compose_derived_qualification(dependent, source)
    answer = composed.answers[0]
    assert answer.conclusion == "inapplicable"
    assert answer.conditions == ("source condition",)
    assert tuple(use.name for use in answer.assumptions_used) == ("source",)
    assert answer.relevant_unsupported_assumptions == ("source unsupported",)
    assert answer.blockers == ("derived target source closed concluded unresolved",)


def test_derived_qualification_overflow_is_unresolved_without_losing_existing_details():
    interpretation = Interpretation(normalized_sympy="34", normalized_latex="34")
    source = ClosedFormResult(
        name="closed", target={"kind": "expression"}, normalized_target=interpretation,
        summary="closed", answers=(QueryAnswer(
            conclusion="unresolved",
            relevant_unsupported_assumptions=tuple(f"source-{index}" for index in range(128)),
            blockers=("source blocker",),
        ),),
    )
    dependent = EquivalenceResult(
        name="dependent", target=DerivedTarget(query="closed"), normalized_target=None,
        summary="unavailable", answers=(QueryAnswer(
            conclusion="inapplicable", relevant_unsupported_assumptions=("dependent",),
            blockers=("derived target source closed concluded unresolved",),
        ),),
    )
    answer = formula_query_service._compose_derived_qualification(dependent, source).answers[0]
    assert answer.conclusion == "unresolved"
    assert answer.blockers == (
        "derived target source closed concluded unresolved",
        "derived target qualification exceeds its bound",
    )
    assert answer.relevant_unsupported_assumptions == ("dependent",)


def test_derived_request_structure_rejects_non_earlier_sources_and_closed_form_consumers():
    invalid_queries = (
        ({"name": "later", "kind": "equivalence", "target": {"kind": "derived", "query": "missing"}, "comparison": "x"},),
        (
            {"name": "dependent", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "x"},
            {"name": "closed", "kind": "closed_form"},
        ),
        (
            {"name": "self", "kind": "equivalence", "target": {"kind": "derived", "query": "self"}, "comparison": "x"},
        ),
        (
            {"name": "not_closed", "kind": "equivalence", "comparison": "x"},
            {"name": "dependent", "kind": "equivalence", "target": {"kind": "derived", "query": "not_closed"}, "comparison": "x"},
        ),
        ({"name": "closed", "kind": "closed_form", "target": {"kind": "derived", "query": "other"}},),
        ({"name": "properties", "kind": "properties", "target": {"kind": "derived", "query": "other"}, "checks": ({"kind": "sign"},)},),
        ({"name": "asymptotic", "kind": "asymptotic", "target": {"kind": "derived", "query": "other"}, "variable": "x", "point": "oo", "order": 1},),
    )
    for queries in invalid_queries:
        with pytest.raises(ValidationError):
            request(queries=queries)


def test_query_result_models_reject_invalid_derived_target_nullability():
    interpretation = Interpretation(normalized_sympy="x", normalized_latex="x")
    answer = QueryAnswer(conclusion="proved", evidence=IdentityEvidence(statement="same"))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="submitted", target={"kind": "expression"}, normalized_target=None, summary="bad", answers=(answer,))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="derived", target={"kind": "derived", "query": "closed"}, normalized_target=None, summary="bad", answers=(answer,))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="unavailable", target={"kind": "derived", "query": "closed"}, normalized_target=interpretation, summary="bad", answers=(QueryAnswer(conclusion="inapplicable", blockers=("derived target source closed concluded unresolved",)),))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="wrong_source", target={"kind": "derived", "query": "closed"}, normalized_target=None, summary="bad", answers=(QueryAnswer(conclusion="inapplicable", blockers=("derived target source other concluded unresolved",)),))
    with pytest.raises(ValidationError):
        EquivalenceResult(name="missing_conclusion", target={"kind": "derived", "query": "closed"}, normalized_target=None, summary="bad", answers=(QueryAnswer(conclusion="inapplicable", blockers=("derived target source closed",)),))


def test_aggregate_work_comparison_owns_unavailable_cost_and_blocker_policy() -> None:
    from py_science.formula.work import (  # pyright: ignore[reportPrivateUsage]
        AggregateWorkComparisonInput,
        compare_aggregate_work,
    )

    available = AggregateWorkComparisonInput(work=IntegerLiteral(1))
    unavailable = AggregateWorkComparisonInput(available=False)
    unknown = AggregateWorkComparisonInput(
        work=IntegerLiteral(1), unknown_costs=frozenset({"opaque"})
    )
    blocked = AggregateWorkComparisonInput(
        work=IntegerLiteral(1), direct_work_blockers=frozenset({"not finite"})
    )

    for operand, blocker in (
        (unavailable, "candidate aggregate direct work is unavailable"),
        (unknown, "unknown primitive costs: opaque"),
        (blocked, "candidate aggregate direct work is unavailable"),
    ):
        relation = compare_aggregate_work(
            available, operand, None, semantic_established=True
        )
        assert relation.status == "unresolved"
        assert relation.delta == (IntegerLiteral(0) if operand is unknown else None)
        assert relation.blockers == (blocker,)

    semantic = compare_aggregate_work(
        available, unknown, None, semantic_established=False
    )
    assert semantic.status == "not_comparable"
    assert semantic.delta == IntegerLiteral(0)
    assert semantic.blockers == ("mapped output semantics are not established",)
