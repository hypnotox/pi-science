import pytest
from py_science.formula import (
    AnalysisRequest,
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
from py_science.formula.expressions import BinaryExpression, InfinityLiteral, RationalLiteral
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
