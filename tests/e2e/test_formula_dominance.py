from py_science.formula import (
    AnalysisFailure,
    DominanceAnalysisRequest,
    FormulaSyntax,
    MathematicalDomain,
    VariableDeclaration,
    analyze_dominance,
)


def test_integer_correction_contract() -> None:
    result = analyze_dominance(
        DominanceAnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x * x",
            axis="x",
            variables={"x": VariableDeclaration(domain=MathematicalDomain.POSITIVE_INTEGER)},
        )
    )
    assert not isinstance(result, AnalysisFailure)
    assert result.kind == "dominance_analysis"
