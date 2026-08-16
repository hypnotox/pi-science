from py_science.formula import AnalysisRequest, EquationRequest, FormulaSyntax, IndexDomain, analyze


def test_named_indexed_equations_reuse_producer_and_sum_work() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="m",
                    expression="Eq(M[b], Sum(x[i] * y[i], (i, 0, n - 1)))",
                    domains={"b": IndexDomain(lower="0", upper="B - 1")},
                ),
                EquationRequest(
                    name="l",
                    expression="Eq(L[b], M[b] + M[b])",
                    domains={"b": IndexDomain(lower="0", upper="B - 1")},
                ),
            ),
        )
    )
    assert outcome.status == "success"
    assert outcome.system is not None
    assert [equation.name for equation in outcome.system.equations] == ["m", "l"]
    assert outcome.system.dependency_edges == (("m", "l"),)
    assert "Max" in outcome.system.equations[0].aggregate_work


def test_cycles_and_unbound_indexes_are_rejected() -> None:
    cycle = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], B[i])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
                EquationRequest(
                    name="b",
                    expression="Eq(B[i], A[i])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
            ),
        )
    )
    assert cycle.status == "failure"
    unbound = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], x[j])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
            ),
        )
    )
    assert unbound.status == "failure"
