# pyright: reportPrivateUsage=false
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_lexical_binding_reuse_candidate_stays_inside_its_scope() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        MathematicalDomain,
        PrimitiveCost,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Let(t, x + 1, f(t) + f(t))",
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            primitive_costs=(PrimitiveCost(name="f", parameters=("z",), work="10"),),
        )
    )

    assert outcome.status == "success"
    suggestion = next(
        item for item in outcome.optimization.suggestions if item.kind == "repeated_call"
    )
    assert suggestion.intermediate is not None
    assert suggestion.intermediate.scope_binders == ("t",)
    assert suggestion.work_before == "22"
    assert suggestion.work_after == "12"


@pytest.mark.parametrize(
    ("expression", "expected_scope", "work_before", "work_after"),
    (
        (
            "Let(a, 2, Let(b, a + 1, f(b) + f(b)))",
            ("a", "b"),
            "8",
            "5",
        ),
        (
            "Let(n, 2, Sum(f(i) + f(i), (i, 0, n)))",
            ("n", "i"),
            "11",
            "8",
        ),
    ),
)
def test_lexical_binding_reuse_resolves_nested_values_and_multiplicity(
    expression: str,
    expected_scope: tuple[str, ...],
    work_before: str,
    work_after: str,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, PrimitiveCost, analyze

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=expression,
            primitive_costs=(PrimitiveCost(name="f", parameters=("z",), work="z"),),
        )
    )

    assert outcome.status == "success"
    suggestion = next(
        item for item in outcome.optimization.suggestions if item.kind == "repeated_call"
    )
    assert suggestion.intermediate is not None
    assert suggestion.intermediate.scope_binders == expected_scope
    assert suggestion.work_before == work_before
    assert suggestion.work_after == work_after


def test_local_optimization_families_publish_only_verified_savings() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    fixtures = {
        "repeated_subexpression": "(x + 1) * (x + 1)",
        "reciprocal_reuse": "1 / x + 1 / x",
        "factoring": "x * y + x * z",
        "redundant_operation_removal": "(x + 0) * y",
        "iterator_invariant_hoisting": "Sum(x * x + i, (i, 0, 3))",
    }
    for family, expression in fixtures.items():
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
        assert outcome.status == "success"
        assert outcome.optimization is not None
        suggestion = next(item for item in outcome.optimization.suggestions if item.kind == family)
        assert suggestion.conclusion in {"proved", "proved_under_assumptions"}
        assert int(suggestion.savings) > 0
        assert int(suggestion.work_before) > int(suggestion.work_after)
        assert not isinstance(
            parse_expression(suggestion.transformations[0].proposed.normalized_sympy), ParseFailure
        )


def test_neutral_redundant_operations_can_reduce_work_to_zero() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    for expression in ("x + 0", "x * 1", "x / 1", "x**1"):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
        assert outcome.status == "success" and outcome.optimization is not None
        suggestion = next(
            item
            for item in outcome.optimization.suggestions
            if item.kind == "redundant_operation_removal"
        )
        assert (suggestion.work_before, suggestion.work_after, suggestion.savings) == (
            "1",
            "0",
            "1",
        )
        assert suggestion.conclusion in {"proved", "proved_under_assumptions"}
        assert suggestion.evidence.kind == "identity"
        assert not isinstance(
            parse_expression(suggestion.transformations[0].proposed.normalized_sympy), ParseFailure
        )
        assert type(suggestion).model_validate_json(suggestion.model_dump_json()) == suggestion


def test_zero_work_optimization_scales_equation_output_multiplicity() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="value",
                    expression="Eq(value[i], x + 0)",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.system is not None and outcome.system.total_work == "4"
    suggestion = next(
        item
        for item in outcome.optimization.suggestions
        if item.kind == "redundant_operation_removal"
    )
    assert (suggestion.work_before, suggestion.work_after, suggestion.savings) == (
        outcome.system.total_work,
        "0",
        outcome.system.total_work,
    )
    assert suggestion.transformations[0].target.name == "value"


def test_repeated_defined_call_is_reused_but_unknown_call_is_omitted() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, FunctionDefinition, analyze

    known = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f(x) + f(x)",
            functions=(FunctionDefinition(name="f", parameters=("z",), body="z * z"),),
        )
    )
    unknown = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="f(x) + f(x)"))
    assert known.status == "success" and known.optimization is not None
    assert any(item.kind == "repeated_call" for item in known.optimization.suggestions)
    assert unknown.status == "success" and unknown.optimization is not None
    assert unknown.optimization.suggestions == ()


def test_scope_collision_reciprocal_conditions_and_incompatible_sums() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    collision = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(optimization_tmp_1 + 1) * (optimization_tmp_1 + 1)",
        )
    )
    reciprocal = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="1 / x + 1 / x"))
    incompatible = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x + 1, (i, 0, 3)) + Sum(x + 1, (j, 0, 3))",
        )
    )
    assert collision.status == "success" and collision.optimization is not None
    assert collision.optimization.suggestions[0].intermediate is not None
    assert collision.optimization.suggestions[0].intermediate.name == "optimization_tmp_2"
    assert reciprocal.status == "success" and reciprocal.optimization is not None
    reuse = next(
        item for item in reciprocal.optimization.suggestions if item.kind == "reciprocal_reuse"
    )
    assert reuse.conditions == ("x != 0",)
    assert incompatible.status == "success" and incompatible.optimization is not None
    assert all(
        item.kind != "repeated_subexpression" for item in incompatible.optimization.suggestions
    )


def test_each_local_family_can_publish_for_an_equation_system() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        VariableDeclaration,
        analyze,
    )

    fixtures = {
        "repeated_subexpression": "(x + 1) * (x + 1)",
        "reciprocal_reuse": "1 / x + 1 / x",
        "factoring": "x * y + x * z",
        "redundant_operation_removal": "(x + 0) * y",
        "iterator_invariant_hoisting": "Sum(x * x + i, (i, 0, 3))",
    }
    variables = {
        name: VariableDeclaration(domain=MathematicalDomain.REAL) for name in ("x", "y", "z")
    }
    for family, expression in fixtures.items():
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                equations=(EquationRequest(name="value", expression=f"Eq(value, {expression})"),),
                variables=variables,
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        suggestion = next(item for item in outcome.optimization.suggestions if item.kind == family)
        assert suggestion.transformations[0].target.kind == "equation"
        assert suggestion.transformations[0].target.name == "value"
        assert int(suggestion.work_before) > int(suggestion.work_after) > 0


def test_output_multiplicity_and_intermediate_scope_are_charged_directly() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="value",
                    expression="Eq(value[i], (x + 1) * (x + 1))",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = next(
        item for item in outcome.optimization.suggestions if item.kind == "repeated_subexpression"
    )
    assert all(item.output_indices == ("i",) for item in suggestion.transformations[0].occurrences)
    assert suggestion.intermediate is not None
    assert suggestion.intermediate.scope_output_indices == ()
    assert (suggestion.work_before, suggestion.work_after, suggestion.savings) == (
        "12",
        "5",
        "7",
    )


def test_indexed_local_intermediate_is_referenced_at_its_output_interface() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="value",
                    expression="Eq(value[i], (x[i] + 1) * (x[i] + 1))",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )

    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = next(
        item for item in outcome.optimization.suggestions if item.kind == "repeated_subexpression"
    )
    assert suggestion.intermediate is not None
    assert suggestion.intermediate.scope_output_indices == ("i",)
    assert "optimization_tmp_1[i]" in suggestion.transformations[0].proposed.normalized_sympy


def test_hoisting_with_no_whole_work_improvement_is_omitted() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x * x + i, (i, 0, 0))",
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    assert all(
        item.kind != "iterator_invariant_hoisting" for item in outcome.optimization.suggestions
    )


def test_repeated_defined_call_can_publish_for_an_equation_system() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        FunctionDefinition,
        MathematicalDomain,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(EquationRequest(name="value", expression="Eq(value, f(x) + f(x))"),),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            functions=(FunctionDefinition(name="f", parameters=("z",), body="z * z"),),
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = next(
        item for item in outcome.optimization.suggestions if item.kind == "repeated_call"
    )
    assert suggestion.transformations[0].target.name == "value"
    assert (suggestion.work_before, suggestion.work_after, suggestion.savings) == (
        "3",
        "2",
        "1",
    )


def test_cross_equation_sharing_and_horner_publish_verified_savings() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    shared = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="left",
                    expression="Eq(left[i], x[i] * x[i] + 1)",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
                EquationRequest(
                    name="right",
                    expression="Eq(right[j], x[j] * x[j] - 1)",
                    domains={"j": IndexDomain(lower="0", upper="3")},
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )
    assert shared.status == "success" and shared.optimization is not None
    sharing = next(
        item for item in shared.optimization.suggestions if item.kind == "cross_equation_sharing"
    )
    assert sharing.intermediate is not None
    assert sharing.intermediate.scope_output_indices == ("i",)
    assert {
        occurrence.output_indices
        for transformation in sharing.transformations
        for occurrence in transformation.occurrences
    } == {("i",), ("j",)}
    assert int(sharing.work_before) > int(sharing.work_after) > 0

    horner = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="2*x**3 + 3*x**2 + 4*x + 5",
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )
    assert horner.status == "success" and horner.optimization is not None
    reformulation = next(item for item in horner.optimization.suggestions if item.kind == "horner")
    assert reformulation.intermediate is None
    assert reformulation.finite_precision_qualification == "exact_symbolic_only"
    assert int(reformulation.work_before) > int(reformulation.work_after) > 0


def test_sharing_refuses_incompatible_interfaces_and_horner_refuses_ambiguity() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        VariableDeclaration,
        analyze,
    )

    incompatible = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="left",
                    expression="Eq(left[i], x[i] * x[i])",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
                EquationRequest(
                    name="right",
                    expression="Eq(right[j], x[j] * x[j])",
                    domains={"j": IndexDomain(lower="0", upper="4")},
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        )
    )
    ambiguous = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x**2 + y**2"))
    assert incompatible.status == "success" and incompatible.optimization is not None
    assert all(
        item.kind != "cross_equation_sharing" for item in incompatible.optimization.suggestions
    )
    assert ambiguous.status == "success" and ambiguous.optimization is not None
    assert all(item.kind != "horner" for item in ambiguous.optimization.suggestions)


def test_cross_equation_domains_distinguish_dependent_and_free_bounds() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="z_dependent",
                    expression="Eq(z_dependent[i,j], x[i,j]*x[i,j] + 1)",
                    domains={
                        "i": IndexDomain(lower="0", upper="N"),
                        "j": IndexDomain(lower="0", upper="i"),
                    },
                ),
                EquationRequest(
                    name="a_free",
                    expression="Eq(a_free[p,q], x[p,q]*x[p,q] - 1)",
                    domains={
                        "p": IndexDomain(lower="0", upper="N"),
                        "q": IndexDomain(lower="0", upper="optimization_index_0"),
                    },
                ),
            ),
            variables={
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "optimization_index_0": VariableDeclaration(
                    domain=MathematicalDomain.NONNEGATIVE_INTEGER
                ),
            },
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )

    assert outcome.status == "success"
    assert all(item.kind != "cross_equation_sharing" for item in outcome.optimization.suggestions)


def test_sharing_covers_scalar_lexical_predecessor_and_producer_dependencies() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    cases = (
        (
            (
                EquationRequest(name="a", expression="Eq(a, x*x + 1)"),
                EquationRequest(name="b", expression="Eq(b, x*x - 1)"),
            ),
            {"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            (),
        ),
        (
            (
                EquationRequest(name="a", expression="Eq(a, Sum(x*x+i, (i, 0, 3)) + 1)"),
                EquationRequest(name="b", expression="Eq(b, Sum(x*x+j, (j, 0, 3)) - 1)"),
            ),
            {"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            (),
        ),
        (
            (
                EquationRequest(
                    name="producer",
                    expression="Eq(p[i], x[i] + 1)",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
                EquationRequest(
                    name="a",
                    expression="Eq(a[i], p[i]*p[i] + 1)",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                ),
                EquationRequest(
                    name="b",
                    expression="Eq(b[j], p[j]*p[j] - 1)",
                    domains={"j": IndexDomain(lower="0", upper="3")},
                ),
            ),
            {"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            ("i",),
        ),
        (
            (
                EquationRequest(
                    name="a",
                    expression="Eq(a[i,j], x[i,j]*x[i,j] + 1)",
                    domains={
                        "i": IndexDomain(lower="0", upper="N"),
                        "j": IndexDomain(lower="0", upper="i"),
                    },
                ),
                EquationRequest(
                    name="b",
                    expression="Eq(b[p,q], x[p,q]*x[p,q] - 1)",
                    domains={
                        "p": IndexDomain(lower="0", upper="N"),
                        "q": IndexDomain(lower="0", upper="p"),
                    },
                ),
            ),
            {
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            },
            ("i", "j"),
        ),
    )
    for equations, variables, expected_scope in cases:
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                equations=equations,
                variables=variables,
                optimization=OptimizationConfig(max_suggestions=16),
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        sharing = next(
            item
            for item in outcome.optimization.suggestions
            if item.kind == "cross_equation_sharing"
        )
        assert sharing.intermediate is not None
        assert sharing.intermediate.scope_output_indices == expected_scope
        assert int(sharing.savings) > 0 if sharing.savings.isdigit() else sharing.savings
        matching_plan = next(
            plan for plan in outcome.optimization.plans if plan.suggestion is sharing
        )
        assert matching_plan.trace[-1].evidence.statement.endswith(
            "every transformed retained output"
        )


def test_sharing_refuses_unequal_arity_constraints_and_uses_collision_free_name() -> None:
    from py_science.formula import (
        AnalysisRequest,
        DomainConstraint,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    refused = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(a[i], x[i]*x[i])",
                    domains={"i": IndexDomain(lower="0", upper="3")},
                    constraints=(DomainConstraint(name="cap", target="i", relationship="i <= 2"),),
                ),
                EquationRequest(
                    name="b",
                    expression="Eq(b[j,k], x[j]*x[j])",
                    domains={
                        "j": IndexDomain(lower="0", upper="3"),
                        "k": IndexDomain(lower="0", upper="1"),
                    },
                ),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        )
    )
    assert refused.status == "success" and refused.optimization is not None
    assert all(item.kind != "cross_equation_sharing" for item in refused.optimization.suggestions)

    collision = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="seed", expression="Eq(optimization_tmp_1, x + 1)"),
                EquationRequest(name="a", expression="Eq(a, x*x + 1)"),
                EquationRequest(name="b", expression="Eq(b, x*x - 1)"),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )
    assert collision.status == "success" and collision.optimization is not None
    sharing = next(
        item for item in collision.optimization.suggestions if item.kind == "cross_equation_sharing"
    )
    assert sharing.intermediate is not None
    assert sharing.intermediate.name == "optimization_tmp_2"


def test_horner_coefficients_bounds_refusals_and_higher_work_filtering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationConfig,
        analyze,
        sympy_backend,
    )

    for expression in (
        "a*x**3 + b*x**2 + c*x + d",
        "(1/2)*x**3 + (2/3)*x**2 + (3/4)*x + 1",
    ):
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=expression,
                optimization=OptimizationConfig(max_suggestions=16),
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        suggestion = next(
            item for item in outcome.optimization.suggestions if item.kind == "horner"
        )
        assert suggestion.conclusion in {"proved", "proved_under_assumptions"}
        assert int(suggestion.work_before) > int(suggestion.work_after) > 0
        assert not isinstance(
            parse_expression(suggestion.transformations[0].proposed.normalized_sympy), ParseFailure
        )

    for expression in ("x**8 + 1", "x*(x*(2*x + 3) + 4) + 5", "x**2 + y**2"):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
        assert outcome.status == "success" and outcome.optimization is not None
        assert all(item.kind != "horner" for item in outcome.optimization.suggestions)
        assert outcome.optimization.status == "complete"

    over_bound = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="2*x**9 + 3*x**8 + 4*x + 5")
    )
    assert over_bound.status == "success" and over_bound.optimization is not None
    assert over_bound.optimization.status == "incomplete"
    assert "measured 9, configured 8" in over_bound.optimization.qualifications[0]

    def refused(*_args: object, **_kwargs: object) -> object:
        raise sympy_backend.sympy.polys.polyerrors.PolynomialError("expected refusal")

    monkeypatch.setattr(sympy_backend.sympy, "horner", refused)
    backend_refused = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="2*x**3 + 3*x**2 + 4*x + 5")
    )
    assert backend_refused.status == "success" and backend_refused.optimization is not None
    assert backend_refused.optimization.status == "incomplete"
    assert backend_refused.optimization.qualifications[0] == "optimization Horner backend refusal"


def test_unexpected_horner_backend_defects_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze, sympy_backend

    def defect(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unexpected Horner defect")

    monkeypatch.setattr(sympy_backend.sympy, "horner", defect)
    result = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="2*x**3 + 3*x**2 + 4*x + 5",
        )
    )
    assert result.status == "success"
    assert result.optimization.status == "failed"


def test_unexpected_factoring_backend_defects_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import sympy_backend

    def defect(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unexpected factoring defect")

    monkeypatch.setattr(sympy_backend.sympy, "factor", defect)
    with pytest.raises(RuntimeError, match="unexpected factoring defect"):
        sympy_backend.bounded_factor_candidate(_expression("x*y + x*z"))
