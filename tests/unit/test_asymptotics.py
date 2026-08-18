# ruff: noqa: E501
# pyright: basic, reportArgumentType=false, reportAttributeAccessIssue=false
"""Phase-5 asymptotic backend seam and boundary regressions."""
import py_science.formula.sympy_backend as sympy_backend
from py_science.formula import (
    AnalysisRequest,
    Assumption,
    FormulaSyntax,
    MathematicalDomain,
    VariableDeclaration,
)
from py_science.formula.service import analyze


def _answer(expression: str, point: str, *, order: int = 1, variable: str = "x", assumptions=(), variables=None):
    request = {"name": "a", "kind": "asymptotic", "variable": variable, "point": point, "order": order}
    if point not in {"oo", "-oo"}:
        request["direction"] = "both"
    result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression, assumptions=assumptions, variables=variables or {}, queries=(request,)))
    assert result.status == "success"
    return result.queries[0].answers[0]


def test_identically_zero_rational_expands_at_every_supported_approach():
    for point in ("0", "oo", "-oo"):
        answer = _answer("0/(y + 1)", point, variable="y", order=8)
        assert answer.conclusion == "proved_under_assumptions"
        assert answer.evidence is not None
        assert "0 = 0 + O(t**8)" in answer.evidence.statement
        assert f"t = {('y - 0' if point == '0' else '1/y' if point == 'oo' else '-1/y')}" in answer.evidence.statement
        assert answer.evidence.remainder is not None


def test_rational_backend_verification_corruption_is_unresolved(monkeypatch):
    monkeypatch.setattr(sympy_backend, "_asymptotic_verify", lambda *_args: False)
    answer = _answer("(x + 1)/(x - 1)", "oo")
    assert answer.conclusion == "unresolved"
    assert answer.blockers == ("asymptotic remainder verification failed",)


def test_exponential_parameter_and_multiple_base_families_are_verified():
    parameter = _answer(
        "(a*x + b)*r**x",
        "oo",
        order=1,
        assumptions=(Assumption(name="positive_r", relationship="r > 0"),),
        variables={
            "a": VariableDeclaration(domain=MathematicalDomain.REAL),
            "b": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
    )
    assert parameter.conclusion == "proved_under_assumptions"
    assert {use.name for use in parameter.assumptions_used} == {"positive_r"}
    assert parameter.evidence is not None and "a*x + b" in parameter.evidence.statement
    undeclared = _answer(
        "(a*x + b)*r**x", "oo", order=1,
        assumptions=(Assumption(name="positive_r", relationship="r > 0"),),
    )
    assert undeclared.conclusion == "unresolved"
    multi_base = _answer("(x + 1)*2**x + (x + 2)*3**x", "-oo", order=4)
    assert multi_base.conclusion == "proved"
    assert multi_base.evidence is not None and multi_base.evidence.remainder is None
    assert multi_base.evidence.statement.index("x + 1") < multi_base.evidence.statement.index("x + 2")


def test_exponential_decomposition_order_counts_source_terms_not_polynomial_parts():
    assert _answer("(x + 1)*2**x", "oo", order=1).conclusion == "proved"
    assert _answer("x*2**x + 3**x", "oo", order=1).conclusion == "unresolved"
    assert _answer("x*2**x + 3**x", "oo", order=2).conclusion == "proved"


def test_rational_variable_name_is_used_for_finite_and_infinite_local_parameters():
    for point, local, approach in (
        ("2", "y - 2", "y -> 2 (both)"),
        ("oo", "1/y", "y -> oo"),
        ("-oo", "-1/y", "y -> -oo"),
    ):
        answer = _answer("(y + 1)/(y - 1)", point, variable="y", order=2)
        assert answer.conclusion == "proved_under_assumptions"
        assert answer.evidence is not None and f"t = {local}" in answer.evidence.statement
        assert approach in answer.conditions


def test_rational_real_parameter_coefficients_are_verified_and_retained():
    declared = {"a": VariableDeclaration(domain=MathematicalDomain.REAL)}
    for expression, point in (("(a*x + 1)/(x - 1)", "oo"), ("a/(1 - x)", "0")):
        answer = _answer(expression, point, order=2, variables=declared)
        assert answer.conclusion == "proved_under_assumptions"
        assert answer.evidence is not None and "a" in answer.evidence.statement
    for expression, point in (("(a*x + 1)/(x - 1)", "oo"), ("a/(1 - x)", "0")):
        assert _answer(expression, point, order=2).conclusion == "unresolved"


def test_exponential_checker_rejects_corrupted_or_oversized_intermediates(monkeypatch):
    monkeypatch.setattr(sympy_backend, "_exponential_value_is_bounded", lambda *_args: False)
    answer = _answer("(x + 1)*2**x", "oo", order=1)
    assert answer.conclusion == "unresolved"
    assert answer.blockers == (
        "asymptotic linear-exponential target exceeds its bounded resource limits; "
        "simplify the linear-exponential target",
    )


def test_exponential_checker_enforces_the_1024_bit_base_cap():
    oversized_base = 1 << 1024
    answer = _answer(f"{oversized_base}**x", "oo", order=1)
    assert answer.conclusion == "unresolved"
    assert answer.blockers == (
        "asymptotic linear-exponential target exceeds its bounded resource limits; "
        "simplify the linear-exponential target",
    )


def test_asymptotic_reports_each_public_family_refusal():
    def blocker(expression: str, *, variables=None) -> str:
        answer = _answer(expression, "oo", variables=variables)
        assert answer.conclusion == "unresolved"
        assert len(answer.blockers) == 1
        return answer.blockers[0]

    real_a = {"a": VariableDeclaration(domain=MathematicalDomain.REAL)}
    for expression, variables, expected in (
        (
            "sin(x)",
            None,
            "asymptotic target is neither a bounded rational expression nor a supported "
            "linear-exponential expression; use a bounded rational or linear-exponential target",
        ),
        (
            "x**9",
            None,
            "asymptotic rational target exceeds bounded rational degree limit: observed 9, "
            "configured 8; use a smaller bounded rational target",
        ),
        (
            "a/(x + 1)",
            None,
            "asymptotic rational parameters are not proved real; declare non-query "
            "parameters real",
        ),
        (
            "1/(x - a)",
            real_a,
            "asymptotic rational denominator depends on non-query parameters; use a "
            "denominator independent of non-query parameters",
        ),
    ):
        assert blocker(expression, variables=variables) == expected


def test_asymptotic_preflight_does_not_misidentify_an_oversized_rational_target():
    terms = ["x"] * 257
    while len(terms) > 1:
        terms = [
            f"({terms[index]} + {terms[index + 1]})"
            if index + 1 < len(terms)
            else terms[index]
            for index in range(0, len(terms), 2)
        ]
    answer = _answer(terms[0], "oo")
    assert answer.conclusion == "unresolved"
    assert answer.blockers == (
        "asymptotic rational target exceeds bounded rational node limit: observed 513, "
        "configured 512; use a smaller bounded rational target",
    )


def test_asymptotic_linear_exponential_backend_refusals_are_reason_specific(monkeypatch):
    # Inject each backend seam after recognition so no public expression has to
    # accidentally reach a particular resource or reconstruction branch.
    with monkeypatch.context() as injected:
        injected.setattr(sympy_backend, "_exp_add_terms", lambda value: [value, value])
        injected.setattr(sympy_backend.sympy, "cancel", lambda *_args: sympy_backend.sympy.Integer(0))
        term_count = _answer("(x + 1)*2**x", "oo", order=1)
    assert term_count.conclusion == "unresolved"
    assert term_count.blockers == (
        "asymptotic linear-exponential term count exceeds its bound: observed 2, configured 1; "
        "reduce the number of linear-exponential terms",
    )

    with monkeypatch.context() as injected:
        injected.setattr(sympy_backend.sympy, "cancel", lambda *_args: sympy_backend.sympy.Integer(1))
        reconstruction = _answer("(x + 1)*2**x", "oo", order=1)
    assert reconstruction.conclusion == "unresolved"
    assert reconstruction.blockers == (
        "asymptotic linear-exponential reconstruction exceeds its bound; "
        "simplify the linear-exponential target",
    )

    with monkeypatch.context() as injected:
        injected.setattr(sympy_backend.sympy, "sstr", lambda *_args, **_kwargs: "x" * 4097)
        rendering = _answer("(x + 1)*2**x", "oo", order=1)
    assert rendering.conclusion == "unresolved"
    assert rendering.blockers == (
        "asymptotic linear-exponential rendering exceeds its bound; "
        "simplify the linear-exponential target",
    )
