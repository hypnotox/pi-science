import pytest
from py_science.formula import (
    AnalysisRequest,
    Assumption,
    DirectedDefinition,
    EquationRequest,
    FormulaSyntax,
    FunctionDefinition,
    IndexDomain,
    IntervalBound,
    MathematicalDomain,
    PrimitiveCost,
    Scenario,
    VariableDeclaration,
    analyze,
)
from pydantic import ValidationError


def declared(
    domain: MathematicalDomain = MathematicalDomain.NONNEGATIVE_INTEGER,
) -> VariableDeclaration:
    return VariableDeclaration(domain=domain)


def test_assumption_replaces_factored_normalized_sum_with_provenance() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="multipoles",
                    expression="Eq(M[b, a], Sum(basis(a, x[i]), (i, 0, n[b] - 1)))",
                    domains={
                        "b": IndexDomain(lower="0", upper="B_leaf - 1"),
                        "a": IndexDomain(lower="0", upper="K(p) - 1"),
                    },
                ),
            ),
            variables={name: declared() for name in ("p", "n", "B_leaf", "N", "x")},
            functions=(FunctionDefinition(name="K", parameters=("z",), body="z**2"),),
            primitive_costs=(PrimitiveCost(name="basis", parameters=("a", "r"), work="1"),),
            assumptions=(
                Assumption(name="occupancy", relationship="Sum(n[b], (b, 0, B_leaf - 1)) == N"),
            ),
        )
    )
    assert result.status == "success"
    assert result.system is not None
    assert result.system.primitive_invocations == {"basis": "N*p**2"}
    assert [item.name for item in result.system.relationships_used] == [
        "function:K",
        "occupancy",
    ]
    assert result.system.unused_assumptions == ()


def test_relationships_share_parser_budget_and_reject_direct_contradictions() -> None:
    contradiction = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + 1",
            variables={"x": declared()},
            assumptions=(
                Assumption(name="one", relationship="x == 1"),
                Assumption(name="two", relationship="x == 2"),
            ),
        )
    )
    oversized = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            assumptions=tuple(
                Assumption(name=f"a{i}", relationship="x == " + "1" * 60_000) for i in range(5)
            ),
        )
    )
    assert contradiction.status == "failure"
    assert "contradictory assumptions" in contradiction.error.message
    assert oversized.status == "failure"
    assert oversized.error.code.value == "expression_too_complex"


def test_unsupported_relationships_are_unresolved_and_unused() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x[i] + 1, (i, 0, N - 1))",
            variables={
                "N": declared(MathematicalDomain.POSITIVE_INTEGER),
                "x": declared(MathematicalDomain.REAL),
            },
            assumptions=(Assumption(name="ordering", relationship="x[i] <= N"),),
        )
    )
    assert result.status == "success"
    assert result.system is not None
    assert result.system.unused_assumptions == ("ordering",)
    assert "inequality inference is unsupported" in " ".join(result.system.unresolved)


def test_inequality_and_domain_contradictions_are_rejected() -> None:
    interval = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared()},
            assumptions=(
                Assumption(name="lower", relationship="x >= 3"),
                Assumption(name="upper", relationship="x < 3"),
            ),
        )
    )
    domain = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.POSITIVE_INTEGER)},
            assumptions=(Assumption(name="zero", relationship="x <= 0"),),
        )
    )
    assert interval.status == "failure"
    assert domain.status == "failure"
    assert "contradictory assumptions" in interval.error.message
    assert "declared domain" in domain.error.message


def test_directed_definitions_reject_cycles() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            definitions=(
                DirectedDefinition(variable="x", expression="y + 1"),
                DirectedDefinition(variable="y", expression="x + 1"),
            ),
        )
    )
    scenario = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(), "y": declared()},
            scenarios=(
                Scenario(
                    name="cycle",
                    definitions=(
                        DirectedDefinition(variable="x", expression="y"),
                        DirectedDefinition(variable="y", expression="x"),
                    ),
                ),
            ),
        )
    )
    assert result.status == "failure"
    assert "directed definitions contain a cycle" in result.error.message
    assert scenario.status == "failure"
    assert "definitions contain a cycle" in scenario.error.message


def test_directed_definitions_apply_in_dependency_order_with_provenance() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(primitive(p), (i, 0, N - 1))",
            variables={
                "N": declared(MathematicalDomain.POSITIVE_INTEGER),
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "q": declared(MathematicalDomain.POSITIVE_INTEGER),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z**2"),),
            definitions=(
                DirectedDefinition(variable="p", expression="q + 1"),
                DirectedDefinition(variable="q", expression="N + 1"),
            ),
        )
    )
    assert result.status == "success"
    assert result.system is not None
    assert "(N + 2)**2" in result.system.total_work
    assert [item.name for item in result.system.relationships_used] == [
        "definition:q",
        "definition:p",
    ]


def test_scenarios_preserve_general_and_report_fixed_choices_asymptotic_and_bounds() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(primitive(p), (i, 0, N - 1))",
            variables={
                "N": declared(MathematicalDomain.POSITIVE_INTEGER),
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z**2"),),
            scenarios=(
                Scenario(name="fixed_p", fixed={"p": 4}, asymptotic=("N",)),
                Scenario(name="joint", asymptotic=("N", "p")),
                Scenario(name="choices", fixed={"N": 10}, choices={"p": (2, 3)}),
                Scenario(
                    name="derived",
                    definitions=(DirectedDefinition(variable="p", expression="N + 1"),),
                    asymptotic=("N",),
                ),
                Scenario(
                    name="bounded", fixed={"p": 2}, bounds={"N": IntervalBound(lower=10, upper=20)}
                ),
            ),
        )
    )
    assert result.status == "success"
    assert result.system is not None
    assert result.system.total_work == "N + N*p**2 - 1"
    by_name = {scenario.name: scenario for scenario in result.scenarios}
    assert by_name["fixed_p"].substituted_work == "17*N - 1"
    assert by_name["fixed_p"].asymptotic == "Theta(N)"
    assert [item.name for item in by_name["fixed_p"].relationships_used] == ["domain:N"]
    assert "declared domain" in " ".join(by_name["fixed_p"].qualifications)
    assert by_name["joint"].asymptotic is None
    assert "multivariate" in " ".join(by_name["joint"].unresolved)
    assert by_name["choices"].choice_work == {"p=2": "49", "p=3": "99"}
    assert by_name["derived"].relationships_used[0].name.startswith("derived:")
    assert by_name["bounded"].interval is not None
    assert [item.name for item in by_name["bounded"].relationships_used] == ["bound:N"]
    assert by_name["bounded"].interval.model_dump() == {
        "lower_work": "49",
        "upper_work": "99",
        "conservative": True,
    }


def test_interval_without_supported_monotonic_region_remains_unresolved() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(N)",
            variables={"N": declared(MathematicalDomain.REAL)},
            primitive_costs=(
                PrimitiveCost(name="primitive", parameters=("z",), work="(z - 10)**2"),
            ),
            scenarios=(
                Scenario(name="negative_range", bounds={"N": IntervalBound(lower=-2, upper=-1)}),
            ),
        )
    )
    assert result.status == "success"
    scenario = result.scenarios[0]
    assert scenario.interval is None
    assert "unproved" in " ".join(scenario.unresolved)


def test_definition_text_shares_the_request_wide_byte_budget() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            definitions=tuple(
                DirectedDefinition(variable=f"d{i}", expression="1" * 60_000) for i in range(5)
            ),
        )
    )
    assert result.status == "failure"
    assert result.error.code.value == "expression_too_complex"


def test_models_are_strict_frozen_and_population_bounded() -> None:
    with pytest.raises(ValidationError):
        Scenario(name="bad", fixed={"p": 1.5})  # type: ignore[dict-item]
    with pytest.raises(ValidationError, match="integer exceeds"):
        Scenario(name="huge", fixed={"p": 1 << 4_000})
    with pytest.raises(ValidationError, match="generated scenario-result"):
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            scenarios=(
                Scenario(
                    name="many_a",
                    choices={"x": tuple(range(20)), "y": tuple(range(10))},
                ),
                Scenario(
                    name="many_b",
                    choices={"x": tuple(range(20)), "y": tuple(range(10))},
                ),
            ),
        )
    conflicting = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={"p": declared(MathematicalDomain.POSITIVE_INTEGER)},
            scenarios=(Scenario(name="conflict", fixed={"p": 0}),),
        )
    )
    assert conflicting.status == "failure"
    assert "contradicts declared domain" in conflicting.error.message
    scenario = Scenario(name="frozen")
    with pytest.raises(ValidationError):
        scenario.name = "changed"  # type: ignore[misc]
