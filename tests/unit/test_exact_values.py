from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
from py_science.formula.exact_values import parse_exact_scalar, render_exact
from py_science.formula.expressions import InfinityLiteral, RationalLiteral
from py_science.formula.parser import ParseFailure, parse_expression


def test_exact_scalars_reduce_render_and_bound() -> None:
    one_half = parse_exact_scalar("1.50")
    reduced = parse_exact_scalar("-6/8")
    zero = parse_exact_scalar("-0.0")
    assert one_half is not None and render_exact(one_half) == "3/2"
    assert reduced is not None and render_exact(reduced) == "-3/4"
    assert zero is not None and render_exact(zero) == "0"
    assert parse_exact_scalar("1" * 1025) is None


def test_formula_decimals_and_infinities_are_exact_values() -> None:
    assert parse_expression("1.50") == RationalLiteral(3, 2)
    assert parse_expression("oo") == InfinityLiteral(1)
    assert parse_expression("-oo") == InfinityLiteral(-1)


def test_infinite_sum_is_structural_but_has_no_finite_direct_work() -> None:
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i], (i, 0, oo))"))  # noqa: E501
    assert outcome.status == "success"
    assert outcome.abstract_work is None
    assert outcome.direct_work_applicability == "not_finite"
    assert outcome.direct_work_blockers == ("infinite iterator has no finite direct-evaluation work",)  # noqa: E501


def test_infinity_is_rejected_as_an_output_bound() -> None:
    # Parser preserves infinity; equation-domain validation exercises the finite-bound rule.
    assert not isinstance(parse_expression("Sum(x[i], (i, 0, oo))"), ParseFailure)
