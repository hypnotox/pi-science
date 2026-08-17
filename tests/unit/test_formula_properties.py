# ruff: noqa: I001
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingParameterType=false
import sympy
import py_science.formula.properties as properties
import py_science.formula.sympy_backend as backend
from py_science.formula import (
    AnalysisRequest,
    FormulaSyntax,
    MathematicalDomain,
    VariableDeclaration,
    analyze,
)


def query(expression, *queries, domain=MathematicalDomain.REAL):
    return analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            variables={"x": VariableDeclaration(domain=domain)},
            queries=queries,
        )
    )


def test_exact_domain_singularities_and_factor_sign_chart():
    outcome = query(
        "(x + 1)/(x - 1)",
        {
            "name": "properties",
            "kind": "properties",
            "checks": (
                {"kind": "valid_domain", "variable": "x"},
                {"kind": "singularities", "variable": "x"},
                {"kind": "sign"},
            ),
        },
    )
    answers = outcome.queries[0].answers
    assert answers[0].conclusion == answers[1].conclusion == answers[2].conclusion == "proved"
    assert answers[0].evidence.value == "exclude 1"
    assert "pole of order 1" in answers[1].evidence.value
    assert answers[2].evidence.intervals


def test_cancelled_roots_are_not_singular_and_directional_poles_are_exact():
    cancelled = query(
        "(x - 1)/(x - 1)",
        {
            "name": "p",
            "kind": "properties",
            "checks": ({"kind": "singularities", "variable": "x"},),
        },
    )
    assert cancelled.queries[0].answers[0].evidence.value == "no singularities"
    for direction, exists, value in (
        ("left", True, "-oo"),
        ("right", True, "oo"),
        ("both", False, None),
    ):
        outcome = query(
            "1/(x - 1)",
            {"name": "l", "kind": "limit", "variable": "x", "point": "1", "direction": direction},
        )
        evidence = outcome.queries[0].answers[0].evidence
        assert evidence.exists is exists and evidence.value == value


def test_exact_substitution_infinity_and_real_integer_monotonicity():
    finite = query(
        "x**2", {"name": "l", "kind": "limit", "variable": "x", "point": "2", "direction": "both"}
    )
    assert finite.queries[0].answers[0].evidence.value == "4"
    infinity = query("x**2", {"name": "l", "kind": "limit", "variable": "x", "point": "-oo"})
    assert infinity.queries[0].answers[0].evidence.value == "oo"
    real = query(
        "x**2",
        {"name": "m", "kind": "properties", "checks": ({"kind": "monotonicity", "variable": "x"},)},
    )
    assert real.queries[0].answers[0].conclusion == "proved"
    integer = query(
        "x**2",
        {"name": "m", "kind": "properties", "checks": ({"kind": "monotonicity", "variable": "x"},)},
        domain=MathematicalDomain.INTEGER,
    )
    assert integer.queries[0].answers[0].conclusion == "proved"
    assert "forward difference" in integer.queries[0].answers[0].evidence.value


def test_afmm_tail_qualifications_preserve_open_q_domain():
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum((k + 1) * q**k, (k, p, oo))",
            variables={
                "p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "q": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
            assumptions=(
                {"name": "q_nonnegative", "relationship": "q >= 0"},
                {"name": "q_converges", "relationship": "q < 1"},
            ),
            queries=(
                {
                    "name": "tail",
                    "kind": "properties",
                    "checks": (
                        {"kind": "sign"},
                        {"kind": "monotonicity", "variable": "p"},
                        {"kind": "monotonicity", "variable": "q"},
                        {"kind": "singularities", "variable": "q"},
                    ),
                },
            ),
        )
    )
    answers = outcome.queries[0].answers
    assert answers[0].evidence.value.startswith("nonnegative")
    assert answers[1].evidence.value.startswith("nonincreasing")
    assert answers[2].evidence.value == "nondecreasing"
    assert "outside the active domain" in answers[3].evidence.value
    assert {use.name for use in answers[1].assumptions_used} == {"q_nonnegative", "q_converges"}


def test_parameter_limits_and_parameter_root_reporting_preserve_provenance():
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="a*x",
        variables={
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            "a": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        assumptions=({"name": "a_positive", "relationship": "a > 0"},),
        queries=(
            {"name": "finite", "kind": "limit", "variable": "x", "point": "2", "direction": "both"},
            {"name": "infinity", "kind": "limit", "variable": "x", "point": "oo"},
        ),
    )
    finite, infinity = analyze(request).queries
    assert finite.answers[0].evidence.value == "2*a"
    assert infinity.answers[0].evidence.value == "oo"
    assert {use.name for use in finite.answers[0].assumptions_used} == {"a_positive"}
    roots = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="1/(x-a)",
        variables=request.variables,
        assumptions=request.assumptions,
        queries=(
            {
                "name": "roots",
                "kind": "properties",
                "checks": (
                    {"kind": "valid_domain", "variable": "x"},
                    {"kind": "singularities", "variable": "x"},
                    {"kind": "sign"},
                    {"kind": "monotonicity", "variable": "x"},
                ),
            },
        ),
    )
    domain, pole, sign, monotonicity = analyze(roots).queries[0].answers
    assert domain.evidence.intervals == ("x != a",)
    assert pole.evidence.value == "x = a: pole of order 1"
    assert sign.conclusion == monotonicity.conclusion == "unresolved"


def test_domain_intersected_chart_uses_interior_witnesses_and_retains_boundaries():
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x - 1",
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            assumptions=(
                {"name": "positive", "relationship": "x > 0"},
                {"name": "bounded", "relationship": "x < 2"},
            ),
            queries=({"name": "p", "kind": "properties", "checks": ({"kind": "sign"},)},),
        )
    )
    answer = outcome.queries[0].answers[0]
    assert answer.evidence.intervals == ("(-oo, 1): negative", "(1, oo): positive", "1: zero")
    assert {use.name for use in answer.assumptions_used} == {"positive", "bounded"}


def test_pole_cofactor_and_complete_monotonicity_partitions():
    limit = query(
        "1/((x - 1)*(1 - x))",
        {"name": "l", "kind": "limit", "variable": "x", "point": "1", "direction": "both"},
    )
    evidence = limit.queries[0].answers[0].evidence
    assert evidence.left == evidence.right == "-oo"
    monotonicity = query(
        "x**2",
        {"name": "m", "kind": "properties", "checks": ({"kind": "monotonicity", "variable": "x"},)},
    )
    assert monotonicity.queries[0].answers[0].evidence.intervals == (
        "(-oo, 0): negative",
        "(0, oo): positive",
        "0: zero",
    )


def test_afmm_tail_exact_family_conditions_and_strictness_variants():
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="Sum(q**k * (1 + k), (k, p, oo))",
        variables={
            "p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "q": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        assumptions=(
            {"name": "q_positive", "relationship": "q > 0"},
            {"name": "q_converges", "relationship": "q < 1"},
        ),
        queries=(
            {
                "name": "tail",
                "kind": "properties",
                "checks": ({"kind": "sign"}, {"kind": "valid_domain", "variable": "q"}),
            },
        ),
    )
    answer = analyze(request).queries[0].answers
    assert answer[0].evidence.value == "strictly positive"
    assert answer[0].conclusion == "proved_under_assumptions"
    assert answer[1].evidence.intervals == ("q != 1",)
    for expression in ("Sum((k + 2) * q**k, (k, p, oo))", "Sum((0 - (k + 1)) * q**k, (k, p, oo))"):
        near = request.model_copy(update={"expression": expression})
        assert analyze(near).queries[0].answers[0].conclusion == "unresolved"
    zero_p = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=request.expression,
        variables=request.variables,
        assumptions=(
            {"name": "q_nonnegative", "relationship": "q >= 0"},
            {"name": "q_converges", "relationship": "q < 1"},
            {"name": "p_upper", "relationship": "p <= 0"},
        ),
        queries=request.queries,
    )
    strict = analyze(zero_p).queries[0].answers[0]
    assert strict.evidence.value == "strictly positive"
    assert {use.name for use in strict.assumptions_used} == {
        "q_nonnegative",
        "q_converges",
        "p_upper",
    }


def test_property_resource_refusal_happens_before_backend_call(monkeypatch):
    called = False

    def forbidden(_):
        nonlocal called
        called = True
        raise AssertionError("backend must not run after target preflight refusal")

    monkeypatch.setattr(properties, "property_value", forbidden)
    oversized = " + ".join("x" for _ in range(513))
    outcome = query(
        oversized,
        {"name": "p", "kind": "properties", "checks": ({"kind": "valid_domain", "variable": "x"},)},
    )
    assert outcome.status == "failure"
    assert outcome.error.code == "expression_too_complex"
    assert called is False


def test_backend_post_transform_bound_and_work_immutability(monkeypatch):
    x = sympy.Symbol("x")
    original = x + 1
    assert backend.property_substitute(original, x, sympy.Integer(2)) == 3
    assert original == x + 1
    monkeypatch.setattr(backend.sympy, "cancel", lambda _: sympy.Integer(2) ** 2048)
    assert backend.property_cancel(x + 1) is None


def test_unsupported_and_inapplicable_remain_distinct():
    opaque = query(
        "f(x)",
        {"name": "p", "kind": "properties", "checks": ({"kind": "valid_domain", "variable": "x"},)},
    )
    assert opaque.queries[0].answers[0].conclusion == "unresolved"
    absent_realness = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            queries=(
                {
                    "name": "p",
                    "kind": "properties",
                    "checks": ({"kind": "monotonicity", "variable": "x"},),
                },
            ),
        )
    )
    assert absent_realness.queries[0].answers[0].conclusion == "inapplicable"
