# ruff: noqa: E501
from py_science.formula import (
    CandidateComparisonRequest,
    CandidateComparisonSuccess,
    CandidateComputation,
    CandidateOutputMapping,
    CandidateTargetReference,
    EquationRequest,
    EquationTarget,
    ExpressionTarget,
    FormulaSyntax,
    IndexDomain,
    MathematicalDomain,
    VariableDeclaration,
    compare_candidates,
)


def test_expression_candidates_prove_equality_and_orient_work_delta() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        candidates=(CandidateComputation(name="first", expression="x + 1"), CandidateComputation(name="second", expression="x + 1 + 1")),
        outputs=(CandidateOutputMapping(name="value", targets=(CandidateTargetReference(candidate="first", target=ExpressionTarget()), CandidateTargetReference(candidate="second", target=ExpressionTarget()))),),
    )
    result = compare_candidates(request)
    assert isinstance(result, CandidateComparisonSuccess)
    assert result.semantic_status == "disproved"
    assert result.work_comparison.status == "not_comparable"


def test_named_producer_expansion_keeps_submitted_work() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        variables={"N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER), "x": VariableDeclaration(domain=MathematicalDomain.REAL), "d": VariableDeclaration(domain=MathematicalDomain.REAL)},
        candidates=(
            CandidateComputation(name="first", equations=(EquationRequest(name="r", expression="Eq(R[i], x / d)", domains={"i": IndexDomain(lower="0", upper="N")}),)),
            CandidateComputation(name="second", equations=(
                EquationRequest(name="q", expression="Eq(Q[j], 1 / d)", domains={"j": IndexDomain(lower="0", upper="N")}),
                EquationRequest(name="y", expression="Eq(Y[j], x * Q[j])", domains={"j": IndexDomain(lower="0", upper="N")}),
            )),
        ),
        outputs=(CandidateOutputMapping(name="value", targets=(CandidateTargetReference(candidate="first", target=EquationTarget(name="r")), CandidateTargetReference(candidate="second", target=EquationTarget(name="y"))),),),
    )
    result = compare_candidates(request)
    assert isinstance(result, CandidateComparisonSuccess)
    assert result.outputs[0].answer.conclusion in {"proved", "proved_under_assumptions"}
    assert result.candidates[0].aggregate_work != result.candidates[1].aggregate_work
