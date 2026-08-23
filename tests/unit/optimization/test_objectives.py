# pyright: reportPrivateUsage=false

import pytest


def test_deterministic_ranking_prefers_unconditional_then_larger_exact_savings() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    unconditional = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="reciprocal", expression="Eq(a, 1/x + 1/x)"),
                EquationRequest(name="polynomial", expression="Eq(b, (y + 1) * (y + 1))"),
            ),
            variables={
                name: VariableDeclaration(domain=MathematicalDomain.REAL) for name in ("x", "y")
            },
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )
    ranked = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1) * (x + 1) + (x + 1) + (y + 1) * (y + 1)",
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )
    assert unconditional.status == "success" and unconditional.optimization is not None
    assert unconditional.optimization.suggestions[0].conclusion == "proved"
    assert ranked.status == "success" and ranked.optimization is not None
    exact_savings = [
        int(item.savings)
        for item in ranked.optimization.suggestions
        if item.conclusion == "proved" and item.savings.isdigit()
    ]
    assert exact_savings == sorted(exact_savings, reverse=True)


def test_comparable_symbolic_savings_rank_by_proof_before_stable_ties() -> None:
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

    equations = tuple(
        EquationRequest(
            name=name,
            expression=f"Eq({name}[{index}], x[{index}]*x[{index}] {operator} 1)",
            domains={index: IndexDomain(lower="0", upper=upper)},
        )
        for name, index, upper, operator in (
            ("a", "i", "N", "+"),
            ("b", "j", "N", "-"),
            ("c", "k", "2*N", "+"),
            ("d", "l", "2*N", "-"),
        )
    )
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=equations,
            variables={
                "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    sharing = [
        plan.trace[0]
        for plan in outcome.optimization.plans
        if len(plan.trace) == 1 and plan.trace[0].kind == "cross_equation_sharing"
    ]
    assert [(item.transformations[0].target.name, item.objective_savings) for item in sharing] == [
        ("c", "2*N + 1"),
        ("a", "N + 1"),
    ]


def test_objective_v1_default_and_weighted_request_shapes() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizeRequest

    ordinary = AnalysisRequest.model_validate(
        {
            "syntax": FormulaSyntax.SYMPY,
            "expression": "x + 1",
            "optimization": {"objective": {"kind": "unit_work_v1"}},
        }
    )
    direct = OptimizeRequest.model_validate(
        {
            "syntax": FormulaSyntax.SYMPY,
            "expression": "x + 1",
            "objective": {
                "kind": "weighted_operations_v1",
                "weights": {
                    "additions": "1",
                    "subtractions": "1",
                    "multiplications": "1",
                    "divisions": "1",
                    "powers": "5/2",
                },
            },
        }
    )
    assert ordinary.optimization.objective.kind == "unit_work_v1"
    assert direct.objective.kind == "weighted_operations_v1"
    assert direct.objective.weights.powers == "5/2"


@pytest.mark.parametrize("weight", ["0", "-1", True, "wat", "1/0"])
def test_objective_v1_rejects_nonpositive_or_malformed_weights(weight: object) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax

    with pytest.raises(ValueError):
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": "x + 1",
                "optimization": {
                    "objective": {
                        "kind": "weighted_operations_v1",
                        "weights": {
                            "additions": weight,
                            "subtractions": "1",
                            "multiplications": "1",
                            "divisions": "1",
                            "powers": "1",
                        },
                    }
                },
            }
        )


def test_objective_v1_rejects_incomplete_extra_and_over_bound_weights() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    weights: dict[str, object] = {
        "additions": "1",
        "subtractions": "1",
        "multiplications": "1",
        "divisions": "1",
        "powers": "1",
    }
    base = {
        "syntax": FormulaSyntax.SYMPY,
        "expression": "x + 1",
        "optimization": {"objective": {"kind": "weighted_operations_v1", "weights": weights}},
    }
    assert AnalysisRequest.model_validate(base).optimization.objective.kind == (
        "weighted_operations_v1"
    )
    for invalid in (
        {**weights, "additions": "1e4097"},
        {key: value for key, value in weights.items() if key != "powers"},
        {**weights, "opaque": "1"},
    ):
        with pytest.raises(ValidationError):
            AnalysisRequest.model_validate(
                {
                    **base,
                    "optimization": {
                        "objective": {
                            "kind": "weighted_operations_v1",
                            "weights": invalid,
                        }
                    },
                }
            )


def test_objective_v1_default_all_one_parity_and_stable_identity() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    expression = "(x + 1)*(x + 1) + (y*z + y*w)"
    default = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
    all_one = analyze(
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": expression,
                "optimization": {
                    "objective": {
                        "kind": "weighted_operations_v1",
                        "weights": {
                            "additions": "1",
                            "subtractions": "1",
                            "multiplications": "1",
                            "divisions": "1",
                            "powers": "1",
                        },
                    }
                },
            }
        )
    )
    assert default.status == "success" and all_one.status == "success"
    assert [plan.identity for plan in default.optimization.plans] == [
        plan.identity for plan in all_one.optimization.plans
    ]
    assert [plan.candidate for plan in default.optimization.plans] == [
        plan.candidate for plan in all_one.optimization.plans
    ]
    assert [item.objective_savings for item in default.optimization.suggestions] == [
        item.objective_savings for item in all_one.optimization.suggestions
    ]


def test_objective_v1_weighted_power_reverses_plan_order() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    expression = "(x + 1)*(x + 1) + (y*z + y*w)"
    default = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
    weighted = analyze(
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": expression,
                "optimization": {
                    "objective": {
                        "kind": "weighted_operations_v1",
                        "weights": {
                            "additions": "1",
                            "subtractions": "1",
                            "multiplications": "1",
                            "divisions": "1",
                            "powers": "5/2",
                        },
                    }
                },
            }
        )
    )
    assert default.status == "success" and weighted.status == "success"
    assert default.optimization.plans[0].objective.kind == "unit_work_v1"
    assert weighted.optimization.plans[0].objective.kind == "weighted_operations_v1"
    assert weighted.optimization.plans[1].suggestion.ordering.relation_to_previous in {
        "previous_proved_superior",
        "deterministic_non_superiority",
    }


def test_objective_v1_opaque_work_keeps_fixed_coefficient_one() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": "f(x) + f(x)",
                "primitive_costs": ({"name": "f", "parameters": ("z",), "work": "5"},),
                "optimization": {
                    "objective": {
                        "kind": "weighted_operations_v1",
                        "weights": {
                            "additions": "2",
                            "subtractions": "2",
                            "multiplications": "2",
                            "divisions": "2",
                            "powers": "2",
                        },
                    }
                },
            }
        )
    )
    assert outcome.status == "success"
    suggestion = outcome.optimization.plans[0].suggestion
    assert suggestion.kind == "repeated_call"
    assert (
        suggestion.objective_before,
        suggestion.objective_after,
        suggestion.objective_savings,
    ) == ("12", "7", "5")


def test_objective_v1_plans_carry_canonical_provenance_and_evidence() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": "(x + 1)*(x + 1) + (y*z + y*w)",
                "optimization": {
                    "objective": {
                        "kind": "weighted_operations_v1",
                        "weights": {
                            "additions": "1",
                            "subtractions": "1",
                            "multiplications": "1",
                            "divisions": "1",
                            "powers": "5/2",
                        },
                    }
                },
            }
        )
    )
    assert outcome.status == "success"
    plan = outcome.optimization.plans[0]
    assert plan.objective.model_dump() == {
        "kind": "weighted_operations_v1",
        "weights": {
            "additions": "1",
            "subtractions": "1",
            "multiplications": "1",
            "divisions": "1",
            "powers": "5/2",
        },
    }
    assert plan.suggestion.objective_before
    assert plan.suggestion.ordering.position == 1
    assert plan.suggestion.ordering.relation_to_previous is None


def test_objective_v1_qualified_mismatches_never_claim_adjacent_superiority() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        RelationshipUse,
        analyze,
    )
    from py_science.formula.expressions import IntegerLiteral
    from py_science.formula.optimization import (
        _Accepted,
        _adjacent_ordering_relation,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1)*(x + 1) + (y*z + y*w)",
    )
    outcome = analyze(request)
    assert outcome.status == "success" and len(outcome.optimization.plans) >= 2
    previous, current = outcome.optimization.plans[:2]
    mismatches = (
        current.suggestion.model_copy(update={"conclusion": "proved_under_assumptions"}),
        current.suggestion.model_copy(update={"conditions": ("x != 0",)}),
        current.suggestion.model_copy(
            update={"assumptions_used": (RelationshipUse(name="positive", relationship="x > 0"),)}
        ),
    )
    for qualified in mismatches:
        assert (
            _adjacent_ordering_relation(
                _Accepted(previous.suggestion, request, IntegerLiteral(2)),
                _Accepted(qualified, request, IntegerLiteral(1)),
                None,  # type: ignore[arg-type]
                _OptimizationBudget(),
            )
            == "deterministic_non_superiority"
        )


def test_objective_v1_comparison_qualifications_never_claim_superiority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._optimization import objectives as objectives_owner
    from py_science.formula.expressions import Symbol
    from py_science.formula.optimization import (
        _Accepted,
        _adjacent_ordering_relation,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1)*(x + 1) + (y*z + y*w)",
    )
    outcome = analyze(request)
    assert outcome.status == "success" and len(outcome.optimization.plans) >= 2
    previous, current = outcome.optimization.plans[:2]

    def qualified_relation(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status="second_lower", conditions=("N > M",), assumptions_used=())

    monkeypatch.setattr(objectives_owner, "compare_aggregate_work", qualified_relation)
    assert (
        _adjacent_ordering_relation(
            _Accepted(
                previous.suggestion.model_copy(update={"objective_savings": "N"}),
                request,
                Symbol("N"),
            ),
            _Accepted(
                current.suggestion.model_copy(update={"objective_savings": "M"}),
                request,
                Symbol("M"),
            ),
            None,  # type: ignore[arg-type]
            _OptimizationBudget(),
        )
        == "deterministic_non_superiority"
    )


def test_objective_v1_result_models_reject_population_drift() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationConfig,
        OptimizationReport,
        OptimizationSuccess,
        analyze,
    )
    from pydantic import ValidationError

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1)*(x + 1) + (y*z + y*w)",
        )
    )
    assert outcome.status == "success" and len(outcome.optimization.plans) >= 2
    plans = outcome.optimization.plans[:2]
    drifted_second = plans[1].model_copy(
        update={
            "suggestion": plans[1].suggestion.model_copy(
                update={"ordering": plans[1].suggestion.ordering.model_copy(update={"position": 3})}
            )
        }
    )
    with pytest.raises(ValidationError):
        OptimizationSuccess(
            requested_limit=3,
            search_status="complete",
            plans=(plans[0], drifted_second),
        )
    with pytest.raises(ValidationError):
        OptimizationReport(
            requested_limit=3,
            status="complete",
            suggestions=(plans[0].suggestion, drifted_second.suggestion),
            plans=(plans[0], drifted_second),
        )

    weighted = OptimizationConfig.model_validate(
        {
            "objective": {
                "kind": "weighted_operations_v1",
                "weights": {
                    "additions": "1",
                    "subtractions": "1",
                    "multiplications": "1",
                    "divisions": "1",
                    "powers": "1",
                },
            }
        }
    ).objective
    objective_drift = plans[1].model_copy(update={"objective": weighted})
    with pytest.raises(ValidationError):
        OptimizationSuccess(
            requested_limit=3,
            search_status="complete",
            plans=(plans[0], objective_drift),
        )
    with pytest.raises(ValidationError):
        OptimizationReport(
            requested_limit=3,
            status="complete",
            suggestions=(plans[0].suggestion, objective_drift.suggestion),
            plans=(plans[0], objective_drift),
        )
