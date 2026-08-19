from py_science.formula import (
    AnalysisFailure,
    DominanceAnalysisRequest,
    DominanceRange,
    FormulaSyntax,
    MathematicalDomain,
    PrimitiveCost,
    VariableDeclaration,
    analyze,
    analyze_dominance,
)


def _request(
    work: str,
    domain: MathematicalDomain = MathematicalDomain.POSITIVE_INTEGER,
) -> DominanceAnalysisRequest:
    return DominanceAnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="cost(N)",
        axis="N",
        variables={"N": VariableDeclaration(domain=domain)},
        primitive_costs=(PrimitiveCost(name="cost", parameters=("N",), work=work),),
    )


def test_integer_correction_contract_and_pair_signs() -> None:
    result = analyze_dominance(_request("N**2 - N + 1"))
    assert not isinstance(result, AnalysisFailure)
    assert result.kind == "dominance_analysis"
    assert [(term.id, term.coefficient) for term in result.terms] == [
        ("power:2", "1"), ("power:1", "-1"), ("power:0", "1")
    ]
    assert result.cells[0].model_dump() == {
        "kind": "integer_point", "value": "1", "dominant": (
            "power:2", "power:1", "power:0"), "blockers": ()}
    assert all(item.sign is not None for item in result.evidence)


def test_cancelled_original_denominator_is_retained_as_an_exclusion() -> None:
    result = analyze_dominance(_request("(N**2 - 1) / (N - 1)", MathematicalDomain.REAL))
    assert not isinstance(result, AnalysisFailure)
    assert result.shared_denominator == "1"
    assert [item.value for item in result.exclusions] == ["1"]
    assert all(
        not (
            getattr(
                cell,
                "upper",
                None) == "1" and getattr(
                cell,
                "upper_inclusive",
                False)) for cell in result.cells)


def test_real_open_endpoint_and_integer_lattice_do_not_fabricate_sentinels() -> None:
    real = analyze_dominance(
        _request(
            "N**2 - N + 1",
            MathematicalDomain.REAL).model_copy(
            update={
                "range": DominanceRange(
                    lower="0",
                    upper="2",
                    lower_inclusive=False,
                    upper_inclusive=True)}))
    integer = analyze_dominance(_request("N**2 - N + 1", MathematicalDomain.INTEGER))
    assert not isinstance(real, AnalysisFailure) and not isinstance(integer, AnalysisFailure)
    assert real.effective_range.lower_inclusive is False
    assert all("1000000000" not in cell.model_dump_json() for cell in integer.cells)


def test_nested_analysis_is_the_independent_ordinary_analysis() -> None:
    request = _request("N**2 - N + 1")
    result = analyze_dominance(request)
    ordinary = analyze(request.analysis_request())
    assert not isinstance(result, AnalysisFailure)
    assert result.analysis == ordinary
