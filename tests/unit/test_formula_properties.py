# ruff: noqa: E501, I001
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingParameterType=false
from py_science.formula import AnalysisRequest, FormulaSyntax, MathematicalDomain, VariableDeclaration, analyze


def query(expression, *queries, domain=MathematicalDomain.REAL):
    return analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=expression,
        variables={"x": VariableDeclaration(domain=domain)},
        queries=queries,
    ))


def test_exact_domain_singularities_and_factor_sign_chart():
    outcome = query("(x + 1)/(x - 1)", {
        "name": "properties", "kind": "properties", "checks": (
            {"kind": "valid_domain", "variable": "x"},
            {"kind": "singularities", "variable": "x"},
            {"kind": "sign"},
        ),
    })
    answers = outcome.queries[0].answers
    assert answers[0].conclusion == answers[1].conclusion == answers[2].conclusion == "proved"
    assert answers[0].evidence.value == "exclude 1"
    assert "pole of order 1" in answers[1].evidence.value
    assert answers[2].evidence.intervals


def test_cancelled_roots_are_not_singular_and_directional_poles_are_exact():
    cancelled = query("(x - 1)/(x - 1)", {"name": "p", "kind": "properties", "checks": ({"kind": "singularities", "variable": "x"},)})
    assert cancelled.queries[0].answers[0].evidence.value == "no singularities"
    for direction, exists, value in (("left", True, "-oo"), ("right", True, "oo"), ("both", False, None)):
        outcome = query("1/(x - 1)", {"name": "l", "kind": "limit", "variable": "x", "point": "1", "direction": direction})
        evidence = outcome.queries[0].answers[0].evidence
        assert evidence.exists is exists and evidence.value == value


def test_exact_substitution_infinity_and_real_integer_monotonicity():
    finite = query("x**2", {"name": "l", "kind": "limit", "variable": "x", "point": "2", "direction": "both"})
    assert finite.queries[0].answers[0].evidence.value == "4"
    infinity = query("x**2", {"name": "l", "kind": "limit", "variable": "x", "point": "-oo"})
    assert infinity.queries[0].answers[0].evidence.value == "oo"
    real = query("x**2", {"name": "m", "kind": "properties", "checks": ({"kind": "monotonicity", "variable": "x"},)})
    assert real.queries[0].answers[0].conclusion == "proved"
    integer = query("x**2", {"name": "m", "kind": "properties", "checks": ({"kind": "monotonicity", "variable": "x"},)}, domain=MathematicalDomain.INTEGER)
    assert integer.queries[0].answers[0].conclusion == "proved"
    assert "forward difference" in integer.queries[0].answers[0].evidence.value


def test_afmm_tail_qualifications_preserve_open_q_domain():
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum((k + 1) * q**k, (k, p, oo))",
        variables={"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER), "q": VariableDeclaration(domain=MathematicalDomain.REAL)},
        assumptions=(
            {"name": "q_nonnegative", "relationship": "q >= 0"},
            {"name": "q_converges", "relationship": "q < 1"},
        ),
        queries=({"name": "tail", "kind": "properties", "checks": (
            {"kind": "sign"}, {"kind": "monotonicity", "variable": "p"},
            {"kind": "monotonicity", "variable": "q"}, {"kind": "singularities", "variable": "q"},
        )},),
    ))
    answers = outcome.queries[0].answers
    assert answers[0].evidence.value.startswith("nonnegative")
    assert answers[1].evidence.value.startswith("nonincreasing")
    assert answers[2].evidence.value == "nondecreasing"
    assert "outside the active domain" in answers[3].evidence.value


def test_unsupported_and_inapplicable_remain_distinct():
    opaque = query("f(x)", {"name": "p", "kind": "properties", "checks": ({"kind": "valid_domain", "variable": "x"},)})
    assert opaque.queries[0].answers[0].conclusion == "unresolved"
    absent_realness = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x", queries=({"name": "p", "kind": "properties", "checks": ({"kind": "monotonicity", "variable": "x"},)},)))
    assert absent_realness.queries[0].answers[0].conclusion == "inapplicable"
