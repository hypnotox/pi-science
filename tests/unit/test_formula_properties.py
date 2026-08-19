# ruff: noqa: I001
from fractions import Fraction
from types import SimpleNamespace
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingParameterType=false
import sympy
import py_science.formula.properties as properties
import py_science.formula.sign_chart as sign_charts
import py_science.formula.sympy_backend as backend
from py_science.formula.parser import parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sign_chart import ExplicitAxis, explicit_axis_sign_chart
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


def test_explicit_axis_structural_chart_retains_roots_poles_points_and_provenance():
    expression = parse_expression("(x + 1) / (x - 1)")
    lower = parse_expression("x > -2")
    chart = properties.structural_sign_chart(
        expression,
        "x",
        ReasoningContext.build(
            {"x": MathematicalDomain.REAL},
            (),
            (SimpleNamespace(name="lower", source="x > -2", value=lower),),
        ),
    )
    assert chart is not None and chart.refusal is None
    assert [(item.value, item.order) for item in chart.roots] == [(Fraction(-1), 1)]
    assert [(item.value, item.order) for item in chart.poles] == [(Fraction(1), 1)]
    assert [(item.left, item.right, item.sign) for item in chart.intervals] == [
        (None, Fraction(-1), 1),
        (Fraction(-1), Fraction(1), -1),
        (Fraction(1), None, 1),
    ]
    assert chart.points[0].value == Fraction(-1) and chart.points[0].sign == 0
    assert [(item.name, item.relationship) for item in chart.provenance] == [
        ("lower", "x > -2")
    ]


def test_structural_chart_retains_canceled_denominators_and_refuses_unknown_roots():
    reasoning = ReasoningContext.build({"x": MathematicalDomain.REAL}, (), ())
    supported = properties.structural_sign_chart(
        parse_expression("(x - 1) / (x - 1)"), "x", reasoning
    )
    unsupported = properties.structural_sign_chart(
        parse_expression("(x**2 + 1) / (x**2 + 1)"), "x", reasoning
    )

    assert supported is not None and supported.refusal is None
    assert [
        (item.value, item.order, item.original_denominator)
        for item in supported.poles
    ] == [(Fraction(1), 1, True)]
    assert unsupported is not None
    assert unsupported.refusal is not None
    assert unsupported.refusal.reason == "original denominator roots are unsupported"

    parameter_reasoning = ReasoningContext.build(
        {"x": MathematicalDomain.REAL, "a": MathematicalDomain.REAL}, (), ()
    )
    moving_root = properties.structural_sign_chart(
        parse_expression("x - a"), "x", parameter_reasoning
    )
    moving_obligation = properties.structural_sign_chart(
        parse_expression("(x - a) / (x - a)"), "x", parameter_reasoning
    )
    assert moving_root.refusal is not None
    assert moving_root.refusal.reason == "exact factor sign chart is unsupported"
    assert moving_obligation.refusal is not None
    assert moving_obligation.refusal.reason == "original denominator roots are unsupported"


def test_structural_chart_honors_axis_kind_roots_and_active_domain():
    integer_reasoning = ReasoningContext.build(
        {"x": MathematicalDomain.INTEGER}, (), ()
    )
    half_root = properties.structural_sign_chart(
        parse_expression("x - 1/2"), "x", integer_reasoning
    )
    assert half_root is not None and half_root.refusal is None
    assert [item.value for item in half_root.roots] == [Fraction(1, 2)]
    assert half_root.points == ()
    assert [item.sign for item in half_root.intervals] == [-1, 1]

    mismatch = explicit_axis_sign_chart(
        sympy.Symbol("x"),
        sympy.Integer(1),
        ExplicitAxis("x", False),
        integer_reasoning,
    )
    assert mismatch.refusal is not None
    assert mismatch.refusal.reason == "explicit axis domain is inconsistent"


def test_structural_chart_keeps_repeated_boundaries_outside_active_domain():
    lower = parse_expression("x >= 0")
    upper = parse_expression("x < 2")
    reasoning = ReasoningContext.build(
        {"x": MathematicalDomain.REAL},
        (),
        (
            SimpleNamespace(name="lower", source="x >= 0", value=lower),
            SimpleNamespace(name="upper", source="x < 2", value=upper),
        ),
    )
    chart = properties.structural_sign_chart(
        parse_expression("(x - 1)**2 / (x + 2)**3"), "x", reasoning
    )

    assert chart.refusal is None
    assert [(item.value, item.order) for item in chart.roots] == [(Fraction(1), 2)]
    assert [(item.value, item.order) for item in chart.poles] == [(Fraction(-2), 3)]
    assert [(item.left, item.right) for item in chart.intervals] == [
        (Fraction(-2), Fraction(1)),
        (Fraction(1), None),
    ]
    assert [item.value for item in chart.points] == [Fraction(1)]
    assert {item.name for item in chart.provenance} == {"lower", "upper"}


def test_structural_chart_localizes_unsupported_factors_and_backend_failure(monkeypatch):
    reasoning = ReasoningContext.build({"x": MathematicalDomain.REAL}, (), ())
    unsupported = properties.structural_sign_chart(
        parse_expression("sin(x)"), "x", reasoning
    )
    assert unsupported is not None and unsupported.refusal is not None

    monkeypatch.setattr(sign_charts, "property_factor_roots", lambda _value, _variable: None)
    refused = explicit_axis_sign_chart(
        sympy.Symbol("x"),
        sympy.Integer(1),
        ExplicitAxis("x", False),
        reasoning,
    )
    assert refused.refusal is not None
    assert refused.refusal.reason == "exact factor sign chart is unsupported"

    def fail_roots(_value, _variable):
        raise RuntimeError("backend failure")

    monkeypatch.setattr(sign_charts, "property_factor_roots", fail_roots)
    failed = explicit_axis_sign_chart(
        sympy.Symbol("x"),
        sympy.Integer(1),
        ExplicitAxis("x", False),
        reasoning,
    )
    assert failed.refusal is not None
    assert failed.refusal.reason == "sign chart backend failed"


def test_integer_fractional_domain_sign_answers_preserve_public_bytes():
    cases = (
        (
            "x - 2",
            {"name": "lower", "relationship": "x >= 1/2"},
            '{"check":{"kind":"sign"},"conclusion":"proved_under_assumptions",'
            '"conditions":[],"assumptions_used":[{"name":"lower",'
            '"relationship":"x >= 1/2"}],"relevant_unsupported_assumptions":[],'
            '"blockers":[],"evidence":{"kind":"property","value":"sign chart",'
            '"intervals":["(-oo, 2): negative","(2, oo): positive","2: zero"]},'
            '"derived_candidates":[],"constraint_uses":[]}',
        ),
        (
            "x",
            {"name": "upper", "relationship": "x < 3/2"},
            '{"check":{"kind":"sign"},"conclusion":"proved_under_assumptions",'
            '"conditions":[],"assumptions_used":[{"name":"upper",'
            '"relationship":"x < 3/2"}],"relevant_unsupported_assumptions":[],'
            '"blockers":[],"evidence":{"kind":"property","value":"sign chart",'
            '"intervals":["(-oo, 0): negative","(0, oo): positive","0: zero"]},'
            '"derived_candidates":[],"constraint_uses":[]}',
        ),
    )
    for expression, assumption, expected in cases:
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=expression,
                variables={
                    "x": VariableDeclaration(domain=MathematicalDomain.INTEGER)
                },
                assumptions=(assumption,),
                queries=(
                    {
                        "name": "p",
                        "kind": "properties",
                        "checks": ({"kind": "sign"},),
                    },
                ),
            )
        )
        assert outcome.queries[0].answers[0].model_dump_json() == expected


def test_ambiguous_implicit_sign_axis_remains_localized():
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + y",
            variables={
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "y": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
            queries=(
                {"name": "p", "kind": "properties", "checks": ({"kind": "sign"},)},
            ),
        )
    )
    answer = outcome.queries[0].answers[0]
    assert answer.conclusion == "unresolved"
    assert "ambiguous" in answer.blockers[0]


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
    assert answers[1].model_dump_json() == (
        '{"check":{"kind":"singularities","variable":"x"},"conclusion":"proved",'
        '"conditions":[],"assumptions_used":[],"relevant_unsupported_assumptions":[],'
        '"blockers":[],"evidence":{"kind":"property",'
        '"value":"x = 1: pole of order 1","intervals":[]},'
        '"derived_candidates":[],"constraint_uses":[]}'
    )
    assert answers[2].model_dump_json() == (
        '{"check":{"kind":"sign"},"conclusion":"proved","conditions":[],'
        '"assumptions_used":[],"relevant_unsupported_assumptions":[],"blockers":[],'
        '"evidence":{"kind":"property","value":"sign chart",'
        '"intervals":["(-oo, -1): positive","(-1, 1): negative",'
        '"(1, oo): positive","-1: zero"]},'
        '"derived_candidates":[],"constraint_uses":[]}'
    )


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
    assert finite.answers[0].assumptions_used == ()
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


def test_phase_four_residual_sign_denominator_ordering_and_provenance():
    def properties(expression, variables, assumptions=(), checks=({"kind": "sign"},)):
        return (
            analyze(
                AnalysisRequest(
                    syntax=FormulaSyntax.SYMPY,
                    expression=expression,
                    variables=variables,
                    assumptions=assumptions,
                    queries=({"name": "p", "kind": "properties", "checks": checks},),
                )
            )
            .queries[0]
            .answers
        )

    real_x = {"x": VariableDeclaration(domain=MathematicalDomain.REAL)}
    for relationship, expected in (("a > 0", "positive"), ("a < 0", "negative")):
        answer = properties(
            "a*x",
            {**real_x, "a": VariableDeclaration(domain=MathematicalDomain.REAL)},
            ({"name": "a_sign", "relationship": relationship},),
        )[0]
        assert answer.conclusion == "proved_under_assumptions"
        assert answer.evidence.intervals[1].endswith(expected)
        assert {use.name for use in answer.assumptions_used} == {"a_sign"}
    varying = properties(
        "(a-1/2)*x",
        {**real_x, "a": VariableDeclaration(domain=MathematicalDomain.REAL)},
        ({"name": "lower", "relationship": "a > 0"}, {"name": "upper", "relationship": "a < 1"}),
    )[0]
    assert varying.conclusion == "unresolved"

    nonzero = properties(
        "x/a",
        {**real_x, "a": VariableDeclaration(domain=MathematicalDomain.REAL)},
        ({"name": "a_positive", "relationship": "a > 0"},),
    )[0]
    assert nonzero.conditions == ("a != 0",)
    assert {use.name for use in nonzero.assumptions_used} == {"a_positive"}
    negative_nonzero = properties(
        "x/a",
        {**real_x, "a": VariableDeclaration(domain=MathematicalDomain.REAL)},
        ({"name": "a_negative", "relationship": "a < 0"},),
    )[0]
    assert negative_nonzero.conditions == ("a != 0",)
    assert {use.name for use in negative_nonzero.assumptions_used} == {"a_negative"}
    unresolved = properties(
        "x/a",
        {**real_x, "a": VariableDeclaration(domain=MathematicalDomain.REAL)},
    )[0]
    assert unresolved.blockers == ("original denominator is not proved nonzero",)

    roots = properties(
        "1/((x-1)*(100000000000000000000*x-100000000000000000001))",
        real_x,
        checks=({"kind": "valid_domain", "variable": "x"},),
    )[0]
    assert roots.evidence.intervals == (
        "x != 1",
        "x != 100000000000000000001/100000000000000000000",
    )

    no_real_sign = (
        analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="x",
                queries=({"name": "p", "kind": "properties", "checks": ({"kind": "sign"},)},),
            )
        )
        .queries[0]
        .answers[0]
    )
    assert no_real_sign.conclusion == "inapplicable"

    limit = (
        analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="x**2",
                variables=real_x,
                assumptions=(
                    {"name": "lower", "relationship": "x > 0"},
                    {"name": "upper", "relationship": "x < 10"},
                ),
                queries=(
                    {
                        "name": "l",
                        "kind": "limit",
                        "variable": "x",
                        "point": "2",
                        "direction": "both",
                    },
                ),
            )
        )
        .queries[0]
        .answers[0]
    )
    assert limit.assumptions_used == ()

    pole = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="a*b/(x-1)",
            variables={
                **real_x,
                "a": VariableDeclaration(domain=MathematicalDomain.REAL),
                "b": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
            assumptions=(
                {"name": "a_positive", "relationship": "a > 0"},
                {"name": "b_negative", "relationship": "b < 0"},
            ),
            queries=(
                {
                    "name": "pole",
                    "kind": "limit",
                    "variable": "x",
                    "point": "1",
                    "direction": "right",
                },
            ),
        )
    ).queries[0]
    assert pole.answers[0].evidence.value == "-oo"
    assert {use.name for use in pole.answers[0].assumptions_used} == {"a_positive", "b_negative"}
    summed_pole = (
        analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="(a+b)/(x-1)",
                variables={
                    **real_x,
                    "a": VariableDeclaration(domain=MathematicalDomain.REAL),
                    "b": VariableDeclaration(domain=MathematicalDomain.REAL),
                },
                assumptions=(
                    {"name": "a_positive", "relationship": "a > 0"},
                    {"name": "b_positive", "relationship": "b > 0"},
                ),
                queries=(
                    {
                        "name": "pole",
                        "kind": "limit",
                        "variable": "x",
                        "point": "1",
                        "direction": "right",
                    },
                ),
            )
        )
        .queries[0]
        .answers[0]
    )
    assert summed_pole.conclusion == "unresolved"
    infinity = (
        analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="a*b*x",
                variables={
                    **real_x,
                    "a": VariableDeclaration(domain=MathematicalDomain.REAL),
                    "b": VariableDeclaration(domain=MathematicalDomain.REAL),
                },
                assumptions=(
                    {"name": "a_positive", "relationship": "a > 0"},
                    {"name": "b_negative", "relationship": "b < 0"},
                ),
                queries=({"name": "infinity", "kind": "limit", "variable": "x", "point": "oo"},),
            )
        )
        .queries[0]
        .answers[0]
    )
    assert infinity.evidence.value == "-oo"
    assert {use.name for use in infinity.assumptions_used} == {"a_positive", "b_negative"}


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


def test_rational_bound_refusals_report_observed_degree_and_recovery():
    properties = query(
        "x**9",
        {"name": "p", "kind": "properties", "checks": ({"kind": "valid_domain", "variable": "x"},)},
    )
    properties_answer = properties.queries[0].answers[0]
    assert properties_answer.conclusion == "unresolved"
    assert properties_answer.blockers == (
        "properties target exceeds bounded rational degree limit: observed 9, configured 8; "
        "use a smaller univariate rational target",
    )

    fixed_order = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="q**12 * (13 - 12*q) / (1 - q)**2",
            variables={"q": VariableDeclaration(domain=MathematicalDomain.REAL)},
            queries=(
                {
                    "name": "p",
                    "kind": "properties",
                    "checks": ({"kind": "valid_domain", "variable": "q"},),
                },
            ),
        )
    )
    fixed_order_answer = fixed_order.queries[0].answers[0]
    assert fixed_order_answer.conclusion == "unresolved"
    assert fixed_order_answer.blockers == (
        "properties target exceeds bounded rational degree limit: observed 12, configured 8; "
        "use a smaller univariate rational target",
    )

    limit = query(
        "x**9",
        {"name": "l", "kind": "limit", "variable": "x", "point": "0", "direction": "both"},
    )
    limit_answer = limit.queries[0].answers[0]
    assert limit_answer.conclusion == "unresolved"
    assert limit_answer.blockers == (
        "limit target exceeds bounded rational degree limit: observed 9, configured 8; "
        "use a smaller univariate rational target",
    )


def test_rational_shape_reasoning_refusal_remains_actionable(monkeypatch):
    def refuse(_self, _expression):
        raise RuntimeError("injected bounded reasoning refusal")

    monkeypatch.setattr(properties.ReasoningContext, "apply", refuse)
    properties_outcome = query(
        "x",
        {
            "name": "p",
            "kind": "properties",
            "checks": ({"kind": "valid_domain", "variable": "x"},),
        },
    )
    properties_answer = properties_outcome.queries[0].answers[0]
    assert properties_answer.conclusion == "unresolved"
    assert properties_answer.blockers == (
        "properties target cannot be prepared by bounded query reasoning; "
        "use a smaller univariate rational target",
    )
    limit_outcome = query(
        "x",
        {
            "name": "l",
            "kind": "limit",
            "variable": "x",
            "point": "0",
            "direction": "both",
        },
    )
    limit_answer = limit_outcome.queries[0].answers[0]
    assert limit_answer.conclusion == "unresolved"
    assert limit_answer.blockers == (
        "limit target cannot be prepared by bounded query reasoning; "
        "use a smaller univariate rational target",
    )


def test_rational_shape_backend_refusals_remain_categorical(monkeypatch):
    def blocker() -> str:
        outcome = query(
            "x",
            {
                "name": "p",
                "kind": "properties",
                "checks": ({"kind": "valid_domain", "variable": "x"},),
            },
        )
        return outcome.queries[0].answers[0].blockers[0]

    monkeypatch.setattr(properties, "property_value", lambda _expression: None)
    assert blocker() == (
        "properties target cannot be translated by the bounded rational backend; "
        "use a smaller univariate rational target"
    )
    monkeypatch.undo()

    monkeypatch.setattr(properties, "property_cancel", lambda _value: None)
    assert blocker() == (
        "properties target cannot be cancelled by the bounded rational backend; "
        "use a smaller univariate rational target"
    )
    monkeypatch.undo()

    monkeypatch.setattr(properties, "property_fraction", lambda _value: None)
    assert blocker() == (
        "properties target cannot be split into a bounded rational fraction; "
        "use a smaller univariate rational target"
    )


def test_sign_property_axis_ambiguity_recommends_one_variable_reduction():
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + y",
            variables={
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "y": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
            queries=({"name": "p", "kind": "properties", "checks": ({"kind": "sign"},)},),
        )
    )
    answer = outcome.queries[0].answers[0]
    assert answer.conclusion == "unresolved"
    assert answer.blockers == (
        "sign property axis is ambiguous; reduce to one unambiguous variable",
    )


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
