import pytest
from py_science.formula import (
    AnalysisRequest,
    AnalysisSuccess,
    Assumption,
    DirectedDefinition,
    EquationRequest,
    FormulaSyntax,
    IndexDomain,
    MathematicalDomain,
    PrimitiveCost,
    Scenario,
    VariableDeclaration,
    analyze,
)
from py_science.formula.exact_values import ExactRational, parse_exact_scalar, render_exact
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    InfinityLiteral,
    IntegerLiteral,
    Let,
    RationalLiteral,
    Symbol,
    substitute,
)
from py_science.formula.parser import ParseFailure, parse_expression
from pydantic import ValidationError


def test_exact_scalars_reduce_render_and_bound() -> None:
    one_half = parse_exact_scalar("1.50")
    reduced = parse_exact_scalar("-6/8")
    zero = parse_exact_scalar("-0.0")
    assert one_half is not None and render_exact(one_half) == "3/2"
    assert reduced is not None and render_exact(reduced) == "-3/4"
    assert zero is not None and render_exact(zero) == "0"
    assert parse_exact_scalar("1" * 1025) is None
    maximum_fraction = f"{'9' * 1024}/{'8' * 1024}"
    assert parse_exact_scalar(maximum_fraction) is not None
    assert parse_exact_scalar(f"-{maximum_fraction}") is not None


def test_let_binding_parses_preserves_structure_and_charges_value_once() -> None:
    parsed = parse_expression("Let(t, x*x, t + t)")
    assert type(parsed).__name__ == "Let"
    outcome = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Let(t, x*x, t + t)")
    )
    assert outcome.status == "success"
    assert outcome.interpretation.normalized_sympy == "Let(t, x*x, t + t)"
    assert outcome.abstract_work == 2


@pytest.mark.parametrize(
    "source",
    (
        "Let(t, x)",
        "Let(t, x, t, x)",
        "Let(x + 1, x, x)",
        "Let(t, t + 1, t)",
    ),
)
def test_let_binding_rejects_malformed_name_and_self_reference(source: str) -> None:
    parsed = parse_expression(source)
    assert isinstance(parsed, ParseFailure)


def test_let_binding_normalized_rendering_preserves_binary_grouping() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Let(t, (x + 1)*2, t/(x - 1))",
        )
    )

    assert outcome.status == "success"
    assert outcome.interpretation.normalized_sympy == "Let(t, (x + 1)*2, t/(x - 1))"
    replay = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=outcome.interpretation.normalized_sympy,
        )
    )
    assert replay.status == "success"
    assert replay.interpretation.normalized_latex == outcome.interpretation.normalized_latex


@pytest.mark.parametrize(
    ("source", "normalized"),
    (
        ("Let(t, 0.5**x, t)", "Let(t, (1/2)**x, t)"),
        ("Let(t, x**0.5, t)", "Let(t, x**(1/2), t)"),
        ("Let(t, (-oo)**x, t)", "Let(t, (-oo)**x, t)"),
    ),
)
def test_let_binding_normalized_power_operands_replay(
    source: str,
    normalized: str,
) -> None:
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=source))

    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.interpretation.normalized_sympy == normalized
    replay = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=outcome.interpretation.normalized_sympy,
        )
    )
    assert isinstance(replay, AnalysisSuccess)
    assert replay.interpretation.normalized_latex == outcome.interpretation.normalized_latex


def test_let_binding_substitution_alpha_renames_to_avoid_capture() -> None:
    substituted = substitute(
        Let("t", IntegerLiteral(0), Symbol("x")),
        {"x": Symbol("t")},
    )
    nested = substitute(
        Let(
            "t",
            IntegerLiteral(0),
            Let(
                "t_let",
                IntegerLiteral(1),
                BinaryExpression(BinaryOperator.ADD, Symbol("x"), Symbol("t")),
            ),
        ),
        {"x": Symbol("t")},
    )

    assert isinstance(substituted, Let)
    assert substituted.name != "t"
    assert substituted.value == IntegerLiteral(0)
    assert substituted.body == Symbol("t")
    assert isinstance(nested, Let)
    assert nested.name not in {"t", "t_let"}
    assert isinstance(nested.body, Let)
    assert nested.body.name == "t_let"


@pytest.mark.parametrize(
    ("expression", "variables"),
    (
        ("Let(x, 1, x)", {"x": VariableDeclaration(domain=MathematicalDomain.REAL)}),
        (
            "Sum(Let(i, x*x, i + i), (i, 0, n))",
            {
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "n": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            },
        ),
        (
            "Let(t, 1, Let(t, 2, t))",
            {},
        ),
    ),
)
def test_let_binding_rejects_nonfresh_names(
    expression: str,
    variables: dict[str, VariableDeclaration],
) -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            variables=variables,
        )
    )

    assert outcome.status == "failure"
    assert "binding name" in outcome.error.message


def test_let_binding_scope_changes_aggregate_multiplicity() -> None:
    inside = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Let(t, x*x, t + t), (i, 0, 2))",
        )
    )
    outside = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Let(t, x*x, Sum(t + t, (i, 0, 2)))",
        )
    )

    assert isinstance(inside, AnalysisSuccess)
    assert isinstance(outside, AnalysisSuccess)
    assert inside.system is not None and outside.system is not None
    assert inside.system.total_work == "8"
    assert outside.system.total_work == "6"


def test_let_binding_system_normalization_and_output_multiplicity_are_preserved() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="out",
                    expression="Eq(y[i], Let(t, x[i]*x[i], t + t))",
                    domains={"i": IndexDomain(lower="0", upper="2")},
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        )
    )

    assert outcome.status == "success"
    assert outcome.interpretation.normalized_sympy == (
        "(Eq(y[i], Let(t, x[i]*x[i], t + t)),)"
    )
    assert outcome.system is not None
    assert outcome.system.equations[0].interpretation.normalized_sympy == (
        "Eq(y[i], Let(t, x[i]*x[i], t + t))"
    )
    assert outcome.system.total_work == "6"


def test_let_binding_retains_nonfinite_aggregate_work() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Let(t, x*x, Sum(t, (i, 0, oo)))",
        )
    )

    assert outcome.status == "success"
    assert outcome.abstract_work is None
    assert outcome.direct_work_applicability == "not_finite"


def test_formula_decimals_and_infinities_are_exact_values() -> None:
    assert parse_expression("1.50") == RationalLiteral(3, 2)
    assert parse_expression("0.12345678901234567890123456789") == RationalLiteral(
        12345678901234567890123456789, 10**29
    )
    unicode_decimal = parse_expression("α + 1.50")  # noqa: RUF001
    assert isinstance(unicode_decimal, BinaryExpression)
    assert unicode_decimal.right == RationalLiteral(3, 2)
    assert parse_expression("oo") == InfinityLiteral(1)
    assert parse_expression("-oo") == InfinityLiteral(-1)


@pytest.mark.parametrize("source", ("1e3", "1.", ".5", "1e-3"))
def test_formula_decimal_tokens_reject_noncanonical_spellings(source: str) -> None:
    assert isinstance(parse_expression(source), ParseFailure)


@pytest.mark.parametrize(
    "source", ("oo(x)", "oo[i]", "Sum(x[i], (oo, 0, n))")
)
def test_infinity_spelling_is_reserved_in_identifier_positions(source: str) -> None:
    assert isinstance(parse_expression(source), ParseFailure)


def test_infinity_spelling_is_reserved_in_request_declarations() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={
                "oo": VariableDeclaration(domain=MathematicalDomain.REAL)
            },
        )
    with pytest.raises(ValidationError):
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            definitions=(DirectedDefinition(variable="oo", expression="1"),),
        )


def test_formula_decimal_tokens_enforce_pre_reduction_digit_bounds() -> None:
    assert isinstance(parse_expression("0." + "0" * 1025), ParseFailure)


def test_exact_ir_constructors_enforce_canonical_invariants() -> None:
    assert ExactRational(6, 8) == ExactRational(3, 4)
    assert ExactRational(0, 9) == ExactRational(0, 1)
    with pytest.raises(ValueError):
        ExactRational(1, 0)
    with pytest.raises(ValueError):
        ExactRational(2**3402, 2**3402)
    assert RationalLiteral(6, 8) == RationalLiteral(3, 4)
    assert RationalLiteral(0, 9) == RationalLiteral(0, 1)
    with pytest.raises(ValueError):
        RationalLiteral(1, 0)
    with pytest.raises(ValueError):
        InfinityLiteral(0)


@pytest.mark.parametrize("expression", ("oo", "oo + 1", "1 / oo"))
def test_infinity_never_reports_finite_direct_work(expression: str) -> None:
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
    assert outcome.status == "success"
    assert outcome.abstract_work is None
    assert outcome.direct_work_applicability == "not_finite"
    assert outcome.direct_work_blockers == (
        "mathematical infinity has no finite direct-evaluation work",
    )


def test_infinite_sum_is_structural_but_has_no_finite_direct_work() -> None:
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i], (i, 0, oo))"))  # noqa: E501
    assert outcome.status == "success"
    assert outcome.abstract_work is None
    assert outcome.direct_work_applicability == "not_finite"
    assert outcome.direct_work_blockers == ("infinite iterator has no finite direct-evaluation work",)  # noqa: E501


def test_infinity_is_rejected_as_an_output_bound() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="values",
                    expression="Eq(y[i], x[i])",
                    domains={"i": IndexDomain(lower="0", upper="oo + 1")},
                ),
            ),
            variables={
                "x": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)
            },
        )
    )
    assert outcome.status == "failure"
    assert outcome.error.source is not None
    assert outcome.error.source.path == "equations[0].domains.i.upper"


def test_infinity_is_rejected_in_finite_primitive_work() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="cost(x)",
            primitive_costs=(PrimitiveCost(name="cost", parameters=("z",), work="oo"),),
        )
    )
    assert outcome.status == "failure"
    assert outcome.error.source is not None
    assert outcome.error.source.path == "primitive_costs[0].work"


@pytest.mark.parametrize(
    "expression", ("n", "n + 1", "2 * n", "Sum(x[i], (i, 0, n))")
)
def test_definition_substitution_reclassifies_direct_work_as_nonfinite(
    expression: str,
) -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            variables={
                "n": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)
            },
            definitions=(DirectedDefinition(variable="n", expression="oo"),),
        )
    )
    assert outcome.status == "success"
    assert outcome.direct_work_applicability == "not_finite"
    assert outcome.abstract_work is None


def test_integral_decimal_assumption_specializes_work_like_an_integer() -> None:
    def specialized(relationship: str) -> str | None:
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="Sum(x[i], (i, 0, n - 1))",
                variables={
                    "n": VariableDeclaration(
                        domain=MathematicalDomain.NONNEGATIVE_INTEGER
                    )
                },
                assumptions=(Assumption(name="fixed", relationship=relationship),),
            )
        )
        assert outcome.status == "success"
        assert outcome.system is not None
        return outcome.system.total_work

    assert specialized("n == 2.0") == specialized("n == 2") == "1"


def test_integral_decimal_exponent_preserves_definition_domain() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x[i], (i, 0, q))",
            variables={
                "m": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "q": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            },
            definitions=(DirectedDefinition(variable="q", expression="m**2.0"),),
        )
    )
    assert outcome.status == "success"
    assert outcome.system is not None
    assert not any("domain preservation is unproved" in item for item in outcome.system.unresolved)


def test_infinity_is_rejected_in_scenario_work_definitions() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x[i], (i, 0, n))",
            variables={
                "n": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)
            },
            scenarios=(
                Scenario(
                    name="infinite",
                    definitions=(DirectedDefinition(variable="n", expression="oo"),),
                ),
            ),
        )
    )
    assert outcome.status == "failure"
    assert outcome.error.source is not None
    assert outcome.error.source.path == "scenarios[0].definitions[0].expression"
