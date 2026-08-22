from typing import Any, cast

import pytest
from py_science.formula import (
    AnalysisRequest,
    AnalysisSuccess,
    Assumption,
    DirectedDefinition,
    EquationRequest,
    EquivalenceQuery,
    FormulaSyntax,
    FunctionDefinition,
    IndexDomain,
    IntervalBound,
    MathematicalDomain,
    OptimizationConfig,
    PrimitiveCost,
    Scenario,
    VariableDeclaration,
    analyze,
)
from pydantic import ValidationError
from sympy import Max, sympify  # type: ignore[import-untyped]
from sympy import Sum as SympySum  # type: ignore[import-untyped]


def declared(
    domain: MathematicalDomain = MathematicalDomain.NONNEGATIVE_INTEGER,
) -> VariableDeclaration:
    return VariableDeclaration(domain=domain)


def assert_iterators_are_lexically_bound(rendered: str) -> None:
    parsed = cast(Any, sympify(rendered))
    assert {symbol.name for symbol in parsed.free_symbols}.isdisjoint({"j", "k"})

    def visit(node: Any, bound: frozenset[str] = frozenset()) -> None:
        if node.func is Max:
            assert {symbol.name for symbol in node.free_symbols}.isdisjoint({"j", "k"} - bound)
        if isinstance(node, SympySum):
            body, *limits = cast(tuple[Any, ...], node.args)
            iterators = frozenset(str(limit[0]) for limit in limits)
            visit(body, bound | iterators)
            for limit in limits:
                for endpoint in limit[1:]:
                    visit(endpoint, bound)
            return
        for child in cast(tuple[Any, ...], node.args):
            visit(child, bound)

    visit(parsed)


def test_lexical_binding_scenario_substitution_preserves_work_once() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Let(t, x*x, t + t)",
            variables={"x": declared(MathematicalDomain.REAL)},
            scenarios=(Scenario(name="fixed", fixed={"x": 2}),),
        )
    )

    assert isinstance(result, AnalysisSuccess)
    assert result.interpretation.normalized_sympy == "Let(t, x*x, t + t)"
    assert result.scenarios[0].substituted_work == "2"


def test_nested_sum_scenarios_eliminate_free_bound_indices() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Sum(x[j] + primitive(k), (j, k, n)), (k, 0, p - 1))",
            variables={"n": declared(), "p": declared(), "x": declared(MathematicalDomain.REAL)},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("value",), work="value"),),
            scenarios=(Scenario(name="fixed_order", fixed={"p": 4}),),
        )
    )

    assert isinstance(result, AnalysisSuccess)
    assert result.system is not None
    assert len(result.scenarios) == 1
    operation_counts = result.system.aggregate_operation_counts
    invocations = result.system.primitive_invocations
    assert operation_counts is not None and invocations is not None
    values = (
        *operation_counts.model_dump().values(),
        result.system.total_work,
        result.system.equations[0].aggregate_work,
        *invocations.values(),
        result.scenarios[0].substituted_work,
    )
    for rendered in values:
        assert rendered is not None
        assert_iterators_are_lexically_bound(rendered)


def test_exact_algorithmic_sum_v1_does_not_change_scenarios() -> None:
    source = "3 + Sum(Sum(i*j + j**2, (j, 0, i)), (i, 0, n))"
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression=source,
        variables={"n": declared()},
        scenarios=(Scenario(name="fixed", fixed={"n": 100}),),
    )
    baseline = analyze(request)
    enabled = analyze(
        request.model_copy(
            update={
                "optimization": OptimizationConfig(
                    max_suggestions=16,
                    enabled_algorithmic_families=("finite_polynomial_sum_v1",),
                )
            }
        )
    )
    assert isinstance(baseline, AnalysisSuccess)
    assert isinstance(enabled, AnalysisSuccess)
    assert enabled.scenarios == baseline.scenarios


def test_general_queries_do_not_fan_out_across_scenarios() -> None:
    baseline = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + 1",
            variables={"x": declared(MathematicalDomain.POSITIVE_INTEGER)},
            scenarios=(Scenario(name="fixed", fixed={"x": 2}),),
        )
    )
    queried = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + 1",
            variables={"x": declared(MathematicalDomain.POSITIVE_INTEGER)},
            scenarios=(Scenario(name="fixed", fixed={"x": 2}),),
            queries=(EquivalenceQuery(name="same", comparison="1 + x"),),
        )
    )
    assert isinstance(baseline, AnalysisSuccess)
    assert isinstance(queried, AnalysisSuccess)
    assert queried.scenarios == baseline.scenarios
    assert len(queried.queries) == 1
    assert queried.queries[0].answers[0].conclusion == "proved"


def test_scenarios_cannot_report_finite_work_for_an_infinite_iterator() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x[i], (i, 0, oo))",
            scenarios=(Scenario(name="attempt"),),
        )
    )
    assert result.status == "failure"
    assert result.error.source is not None
    assert result.error.source.path == "scenarios"
    assert result.error.supported_alternative == (
        "remove scenarios to inspect non-finite mathematical structure"
    )


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


@pytest.mark.parametrize(
    "relationship",
    ("1 == 2", "1 + 1 == 3", "1 < 1", "2 <= 1", "1 > 2", "1 >= 2"),
)
def test_false_literal_relationships_fail_before_report_construction(
    relationship: str,
) -> None:
    failed = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(N)",
            variables={"N": declared()},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            assumptions=(Assumption(name="false_literal", relationship=relationship),),
        )
    )
    unaffected = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(N)",
            variables={"N": declared()},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
        )
    )

    assert failed.status == "failure"
    assert failed.error.code.value == "invalid_system"
    assert "false literal relationship" in failed.error.message
    assert unaffected.status == "success"
    assert unaffected.system is not None
    assert unaffected.system.primitive_invocations == {"primitive": "1"}
    assert unaffected.system.total_work == "N"


def test_directly_empty_integer_assumption_interval_is_rejected() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="N",
            variables={"N": declared(MathematicalDomain.INTEGER)},
            assumptions=(
                Assumption(name="lower", relationship="N > 1"),
                Assumption(name="upper", relationship="N < 2"),
            ),
        )
    )

    assert result.status == "failure"
    assert "empty integer interval" in result.error.message


def test_arithmetic_constant_assumptions_respect_declared_integer_domains() -> None:
    fractional = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="N",
            variables={"N": declared(MathematicalDomain.INTEGER)},
            assumptions=(Assumption(name="fraction", relationship="N == 1 / 2"),),
        )
    )
    negative = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="N",
            variables={"N": declared(MathematicalDomain.POSITIVE_INTEGER)},
            assumptions=(Assumption(name="negative", relationship="N == 1 - 2"),),
        )
    )
    empty = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="N",
            variables={"N": declared(MathematicalDomain.INTEGER)},
            assumptions=(
                Assumption(name="lower", relationship="N > 1 + 1"),
                Assumption(name="upper", relationship="N < 3"),
            ),
        )
    )
    assert fractional.status == "failure"
    assert negative.status == "failure"
    assert empty.status == "failure"
    assert "empty integer interval" in fractional.error.message
    assert "declared domain" in negative.error.message
    assert "empty integer interval" in empty.error.message


def test_equality_replacement_is_canonical_and_never_replaces_literals() -> None:
    def outcome(relationship: str):  # type: ignore[no-untyped-def]
        return analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="primitive(N)",
                variables={"N": declared(), "p": declared()},
                primitive_costs=(
                    PrimitiveCost(name="primitive", parameters=("z",), work="z"),
                ),
                assumptions=(Assumption(name="value", relationship=relationship),),
            )
        )

    forward = outcome("N == 1")
    reverse = outcome("1 == N")
    ambiguous = outcome("N == p")
    true_literal = outcome("1 == 1")

    for result in (forward, reverse):
        assert result.status == "success"
        assert result.system is not None
        assert result.system.total_work == "1"
        assert [item.name for item in result.system.relationships_used] == ["value"]
    assert ambiguous.status == "success"
    assert ambiguous.system is not None
    assert ambiguous.system.total_work == "N"
    assert ambiguous.system.relationships_used == ()
    assert ambiguous.system.unused_assumptions == ("value",)
    assert "ambiguous equality" in " ".join(ambiguous.system.unresolved)
    assert true_literal.status == "success"
    assert true_literal.system is not None
    assert true_literal.system.total_work == "N"
    assert true_literal.system.relationships_used == ()
    assert true_literal.system.unresolved == ()


def test_assumption_replacement_respects_bound_sum_indices() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="indexed_work",
                    expression="Eq(A[i], primitive(i))",
                    domains={"i": IndexDomain(lower="0", upper="N - 1")},
                ),
            ),
            variables={"N": declared(MathematicalDomain.POSITIVE_INTEGER)},
            primitive_costs=(
                PrimitiveCost(name="primitive", parameters=("z",), work="z"),
            ),
            assumptions=(Assumption(name="free_i", relationship="i == 1"),),
        )
    )

    assert result.status == "success"
    assert result.system is not None
    assert result.system.total_work == "N*(N - 1)/2"
    assert result.system.relationships_used == ()
    assert result.system.unused_assumptions == ("free_i",)


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


def test_definition_dependencies_ignore_bound_sum_indices() -> None:
    definitions = (
        DirectedDefinition(variable="i", expression="r"),
        DirectedDefinition(variable="r", expression="Sum(x[i], (i, 0, N - 1))"),
    )
    variables = {
        "N": declared(MathematicalDomain.POSITIVE_INTEGER),
        "x": declared(MathematicalDomain.REAL),
        "i": declared(MathematicalDomain.REAL),
        "r": declared(MathematicalDomain.REAL),
    }
    primitive = (PrimitiveCost(name="primitive", parameters=("z",), work="z"),)
    global_result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(i)",
            variables=variables,
            primitive_costs=primitive,
            definitions=definitions,
        )
    )
    scenario_result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(i)",
            variables=variables,
            primitive_costs=primitive,
            scenarios=(Scenario(name="derived", definitions=definitions),),
        )
    )

    assert global_result.status == "success"
    assert global_result.system is not None
    assert global_result.system.total_work == "Sum(x[i], (i, 0, N - 1))"
    assert scenario_result.status == "success"
    assert scenario_result.scenarios[0].substituted_work == "Sum(x[i], (i, 0, N - 1))"


def test_definitions_validate_declared_domains_globally_and_per_scenario() -> None:
    global_contradiction = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={"p": declared(MathematicalDomain.POSITIVE_INTEGER)},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            definitions=(DirectedDefinition(variable="p", expression="-1"),),
        )
    )
    nonintegral_contradiction = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={"p": declared(MathematicalDomain.INTEGER)},
            definitions=(DirectedDefinition(variable="p", expression="1 / 2"),),
        )
    )
    scenario_contradiction = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={"p": declared(MathematicalDomain.POSITIVE_INTEGER)},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            scenarios=(
                Scenario(
                    name="invalid",
                    definitions=(DirectedDefinition(variable="p", expression="-1"),),
                ),
            ),
        )
    )
    undeclared_reference = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={"p": declared()},
            definitions=(DirectedDefinition(variable="p", expression="q + 1"),),
        )
    )
    undeclared_target = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={"p": declared()},
            definitions=(DirectedDefinition(variable="q", expression="1"),),
        )
    )
    global_unproved = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "x": declared(MathematicalDomain.REAL),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            definitions=(DirectedDefinition(variable="p", expression="x"),),
        )
    )
    scenario_unproved = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "x": declared(MathematicalDomain.REAL),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            scenarios=(
                Scenario(
                    name="unproved",
                    definitions=(DirectedDefinition(variable="p", expression="x"),),
                ),
            ),
        )
    )

    assert global_contradiction.status == "failure"
    assert "contradicts declared domain for p" in global_contradiction.error.message
    assert global_contradiction.error.source is not None
    assert global_contradiction.error.source.path == "definitions[0].expression"
    assert global_contradiction.error.location is None
    assert global_contradiction.error.source.span is None
    assert nonintegral_contradiction.status == "failure"
    assert "contradicts declared domain for p" in nonintegral_contradiction.error.message
    assert nonintegral_contradiction.error.source is not None
    assert nonintegral_contradiction.error.source.path == "definitions[0].expression"
    assert nonintegral_contradiction.error.location is None
    assert nonintegral_contradiction.error.source.span is None
    assert scenario_contradiction.status == "failure"
    assert "contradicts declared domain for p" in scenario_contradiction.error.message
    assert undeclared_reference.status == "failure"
    assert "undeclared variables: q" in undeclared_reference.error.message
    assert undeclared_reference.error.source is not None
    assert undeclared_reference.error.source.path == "definitions[0].expression"
    assert undeclared_reference.error.location is None
    assert undeclared_reference.error.source.span is None
    assert undeclared_target.status == "failure"
    assert "definition target q is undeclared" in undeclared_target.error.message
    assert undeclared_target.error.source is not None
    assert undeclared_target.error.source.path == "definitions[0].variable"
    assert undeclared_target.error.location is None
    assert undeclared_target.error.source.span is None
    assert global_unproved.status == "success"
    assert global_unproved.system is not None
    assert "domain preservation is unproved" in " ".join(global_unproved.system.unresolved)
    assert scenario_unproved.status == "success"
    assert "domain preservation is unproved" in " ".join(scenario_unproved.scenarios[0].unresolved)


def test_definition_domains_are_validated_after_dependencies_and_scenario_values() -> None:
    global_dependency = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "q": declared(MathematicalDomain.INTEGER),
            },
            definitions=(
                DirectedDefinition(variable="p", expression="q"),
                DirectedDefinition(variable="q", expression="-1"),
            ),
        )
    )
    scenario_fixed = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "x": declared(MathematicalDomain.REAL),
            },
            scenarios=(
                Scenario(
                    name="fixed_dependency",
                    fixed={"x": -1},
                    definitions=(DirectedDefinition(variable="p", expression="x"),),
                ),
            ),
        )
    )
    scenario_choice = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "x": declared(MathematicalDomain.INTEGER),
            },
            scenarios=(
                Scenario(
                    name="choice_dependency",
                    choices={"x": (-1, 2)},
                    definitions=(DirectedDefinition(variable="p", expression="x"),),
                ),
            ),
        )
    )
    direct_fixed = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={"p": declared(MathematicalDomain.POSITIVE_INTEGER)},
            scenarios=(Scenario(name="invalid_fixed", fixed={"p": -1}),),
        )
    )
    for result in (global_dependency, scenario_fixed, scenario_choice, direct_fixed):
        assert result.status == "failure"
        assert "contradicts declared domain" in result.error.message


def test_scenarios_compose_with_global_definitions_and_reject_overlapping_treatments() -> None:
    dependency = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(q)",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "q": declared(MathematicalDomain.POSITIVE_INTEGER),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            definitions=(DirectedDefinition(variable="p", expression="2"),),
            scenarios=(
                Scenario(
                    name="uses_global",
                    definitions=(DirectedDefinition(variable="q", expression="p + 1"),),
                ),
            ),
        )
    )
    conflict = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p",
            variables={"p": declared(MathematicalDomain.POSITIVE_INTEGER)},
            definitions=(DirectedDefinition(variable="p", expression="2"),),
            scenarios=(Scenario(name="conflict", fixed={"p": 3}),),
        )
    )

    assert dependency.status == "success"
    assert dependency.scenarios[0].substituted_work == "3"
    assert dependency.scenarios[0].substitutions == {"q": "3"}
    assert [item.name for item in dependency.scenarios[0].relationships_used] == [
        "derived:q"
    ]
    assert conflict.status == "failure"
    assert "treatments conflict with global definitions: p" in conflict.error.message


def test_scenario_values_close_symbolic_global_definitions_before_use() -> None:
    composed = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(r)",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "q": declared(MathematicalDomain.INTEGER),
                "r": declared(MathematicalDomain.POSITIVE_INTEGER),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            definitions=(DirectedDefinition(variable="p", expression="q + 1"),),
            scenarios=(
                Scenario(
                    name="closed",
                    fixed={"q": 2},
                    definitions=(DirectedDefinition(variable="r", expression="p + 1"),),
                ),
            ),
        )
    )
    contradiction = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "q": declared(MathematicalDomain.INTEGER),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            definitions=(DirectedDefinition(variable="p", expression="q + 1"),),
            scenarios=(Scenario(name="invalid", fixed={"q": -2}),),
        )
    )

    assert composed.status == "success"
    assert composed.scenarios[0].substituted_work == "4"
    assert composed.scenarios[0].substitutions == {"q": "2", "r": "4"}
    assert contradiction.status == "failure"
    assert "contradicts declared domain for p" in contradiction.error.message


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
    assert result.system.total_work is not None
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
    assert by_name["fixed_p"].choice_work == {}
    assert by_name["fixed_p"].asymptotic == "Theta(N)"
    assert [item.name for item in by_name["fixed_p"].relationships_used] == ["domain:N"]
    assert "declared domain" in " ".join(by_name["fixed_p"].qualifications)
    assert by_name["joint"].asymptotic is None
    assert "multivariate" in " ".join(by_name["joint"].unresolved)
    assert by_name["choices"].choice_work == {"p=2": "49", "p=3": "99"}
    assert by_name["joint"].choice_work == {}
    assert by_name["derived"].choice_work == {}
    assert by_name["derived"].relationships_used[0].name.startswith("derived:")
    assert by_name["bounded"].choice_work == {}
    assert by_name["bounded"].interval is not None
    assert [item.name for item in by_name["bounded"].relationships_used] == ["bound:N"]
    assert by_name["bounded"].interval.model_dump() == {
        "lower": "10",
        "upper": "20",
        "lower_inclusive": True,
        "upper_inclusive": True,
        "lower_work": "49",
        "upper_work": "99",
        "infimum": "49",
        "supremum": "99",
        "infimum_attained": True,
        "supremum_attained": True,
        "conservative": True,
    }


def test_non_choice_scenario_forms_have_no_synthetic_choice_entry() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={
                "p": declared(MathematicalDomain.POSITIVE_INTEGER),
                "N": declared(MathematicalDomain.POSITIVE_INTEGER),
            },
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            scenarios=(
                Scenario(name="fixed", fixed={"p": 2}),
                Scenario(
                    name="derived",
                    definitions=(DirectedDefinition(variable="p", expression="N + 1"),),
                ),
                Scenario(name="asymptotic", asymptotic=("p",)),
                Scenario(name="interval", bounds={"p": IntervalBound(lower=1, upper=3)}),
            ),
        )
    )

    assert result.status == "success"
    assert {scenario.name: scenario.choice_work for scenario in result.scenarios} == {
        "fixed": {},
        "derived": {},
        "asymptotic": {},
        "interval": {},
    }


def test_scenario_definition_provenance_only_claims_changed_work() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(p)",
            variables={"p": declared(), "q": declared(), "N": declared()},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
            scenarios=(
                Scenario(
                    name="used",
                    definitions=(DirectedDefinition(variable="p", expression="N + 1"),),
                ),
                Scenario(
                    name="unused",
                    definitions=(DirectedDefinition(variable="q", expression="N + 1"),),
                ),
            ),
        )
    )

    assert result.status == "success"
    used, unused = result.scenarios
    assert [item.name for item in used.relationships_used] == ["derived:p"]
    assert used.substitutions["p"] == "N + 1"
    assert unused.relationships_used == ()
    assert unused.substitutions["q"] == "N + 1"


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
    with pytest.raises(ValidationError, match="JavaScript-safe"):
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


@pytest.mark.parametrize(
    ("source", "canonical"),
    ((0, "0"), ("-0", "0"), ("1/2", "1/2"), ("-3/4", "-3/4"), ("1.20", "6/5")),
)
def test_scenario_scalars_are_exact_and_canonical(source: str | int, canonical: str) -> None:
    assert Scenario(name="exact", fixed={"x": source}).fixed == {"x": canonical}


@pytest.mark.parametrize("source", (" 1", "+1", "01", ".5", "1.", "1e-3", "1/-2", "1/0"))
def test_scenario_scalars_reject_noncanonical_grammar(source: str) -> None:
    with pytest.raises(ValidationError):
        Scenario(name="invalid", fixed={"x": source})


def test_scenarios_reject_duplicate_canonical_choices_and_honor_open_real_intervals() -> None:
    with pytest.raises(ValidationError, match="unique"):
        Scenario(name="duplicate", choices={"x": ("1/2", "0.5")})
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="primitive(x)",
            variables={"x": declared(MathematicalDomain.NONNEGATIVE_REAL)},
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z + 1"),),
            scenarios=(
                Scenario(
                    name="open",
                    bounds={"x": IntervalBound(lower="-0", upper="1.20", lower_inclusive=False)},
                ),
            ),
        )
    )
    assert result.status == "success"
    interval = result.scenarios[0].interval
    assert interval is not None
    assert interval.lower == "0"
    assert interval.upper == "6/5"
    assert not interval.infimum_attained
    assert interval.supremum_attained


def test_exact_scenario_intervals_intersect_domains_and_global_affine_facts() -> None:
    positive_real = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.POSITIVE_REAL)},
            scenarios=(
                Scenario(name="crosses_zero", bounds={"x": IntervalBound(lower=-1, upper=1)}),
            ),
        )
    )
    integer = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.INTEGER)},
            scenarios=(
                Scenario(
                    name="contains_integer",
                    bounds={"x": IntervalBound(lower="1/2", upper="3/2")},
                ),
            ),
        )
    )
    equality_outside = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.REAL)},
            assumptions=(Assumption(name="fixed", relationship="x == 2"),),
            scenarios=(
                Scenario(name="misses_fixed", bounds={"x": IntervalBound(lower=0, upper=1)}),
            ),
        )
    )
    equality_domain_conflict = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.NONNEGATIVE_REAL)},
            assumptions=(Assumption(name="negative", relationship="x == -1"),),
            scenarios=(
                Scenario(name="conflicts_domain", bounds={"x": IntervalBound(lower=-1, upper=1)}),
            ),
        )
    )
    affine_outside = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.REAL)},
            assumptions=(Assumption(name="positive", relationship="x + 1 > 0"),),
            scenarios=(
                Scenario(name="misses_affine", bounds={"x": IntervalBound(lower=-3, upper=-2)}),
            ),
        )
    )

    assert positive_real.status == "success"
    assert integer.status == "success"
    assert equality_outside.status == "failure"
    assert "global assumptions" in equality_outside.error.message
    assert equality_domain_conflict.status == "failure"
    assert "global assumptions" in equality_domain_conflict.error.message
    assert affine_outside.status == "failure"
    assert "global assumptions" in affine_outside.error.message


def test_negative_definition_contradicts_nonnegative_real_domain() -> None:
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.NONNEGATIVE_REAL)},
            scenarios=(
                Scenario(
                    name="negative_definition",
                    definitions=(DirectedDefinition(variable="x", expression="-1"),),
                ),
            ),
        )
    )

    assert result.status == "failure"
    assert "contradicts declared domain" in result.error.message


def test_scenario_values_and_intervals_must_intersect_assumptions() -> None:
    fixed = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.REAL)},
            assumptions=(Assumption(name="positive", relationship="x > 0"),),
            scenarios=(Scenario(name="bad", fixed={"x": "-1/2"}),),
        )
    )
    interval = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            variables={"x": declared(MathematicalDomain.REAL)},
            assumptions=(Assumption(name="positive", relationship="x > 0"),),
            scenarios=(Scenario(name="bad", bounds={"x": IntervalBound(lower="-2", upper="0")}),),
        )
    )
    assert fixed.status == "failure"
    assert "assumption positive" in fixed.error.message
    assert interval.status == "failure"
    assert "global assumptions" in interval.error.message
