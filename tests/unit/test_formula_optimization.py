# pyright: reportPrivateUsage=false
from dataclasses import FrozenInstanceError
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.optimization import (
    _detect_occurrences,
    _extraction_opportunities,
    _TraversalExhausted,
)
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_typed_occurrences_keep_paths_free_symbols_and_sum_scope() -> None:
    expression = _expression("Sum(x[i] + 1, (i, 0, N)) + Sum(x[i] + 1, (i, 0, N))")

    occurrences = _detect_occurrences("out", expression, {}, output_indices=("j",))
    repeated = [item for item in occurrences if item.path in {(0, 2), (1, 2)}]

    assert [(item.target, item.path) for item in repeated] == [
        ("out", (0, 2)),
        ("out", (1, 2)),
    ]
    assert all(item.binders == ("i",) for item in repeated)
    assert all(item.scope.output_indices == ("j",) for item in repeated)
    assert all(item.free_symbols == frozenset({"x"}) for item in repeated)
    assert repeated[0].scope.binders != repeated[1].scope.binders
    with pytest.raises(FrozenInstanceError):
        repeated[0].path = ()  # type: ignore[misc]


def test_lexical_binding_occurrences_keep_value_and_body_scopes_distinct() -> None:
    occurrences = _detect_occurrences(
        "out",
        _expression("Let(t, x[i]*x[i], t + t)"),
        {},
        output_indices=("i",),
    )

    binding = next(item for item in occurrences if item.path == ())
    value = next(item for item in occurrences if item.path == (0,))
    body = next(item for item in occurrences if item.path == (1,))
    assert binding.free_symbols == frozenset({"x"})
    assert value.free_symbols == frozenset({"x"})
    assert body.free_symbols == frozenset()
    assert binding.binders == value.binders == ()
    assert body.binders == ("t",)
    assert tuple(item.name for item in body.scope.binders) == ("t",)


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


def test_output_indices_are_bound_and_domains_distinguish_evaluation_scopes() -> None:
    expression = _expression("x[i] + 1")
    lower, upper_n, upper_m = _expression("0"), _expression("N"), _expression("M")

    with_n = _detect_occurrences(
        "out",
        expression,
        {},
        output_indices=("i",),
        output_domains={"i": (lower, upper_n)},
    )[0]
    with_m = _detect_occurrences(
        "out",
        expression,
        {},
        output_indices=("i",),
        output_domains={"i": (lower, upper_m)},
    )[0]

    assert with_n.free_symbols == frozenset({"x"})
    assert with_n.scope.output_bindings[0].upper == upper_n
    assert with_n.scope != with_m.scope


def test_shadowed_binders_keep_lexical_identity_and_capture_context() -> None:
    expression = _expression("Sum(Sum(x[i] + 1, (i, 0, M)), (i, 0, N))")

    body = next(
        item
        for item in _detect_occurrences("out", expression, {}, output_indices=("i",))
        if item.path == (2, 2)
    )

    assert body.binders == ("i", "i")
    assert tuple(binding.path for binding in body.scope.binders) == ((), (2,))
    assert body.scope.output_indices == ("i",)
    assert body.free_symbols == frozenset({"x"})


def test_call_paths_and_named_producer_index_paths_are_observable() -> None:
    call = _detect_occurrences("out", _expression("f(x + 1)"), {})
    assert [(item.path, type(item.expression).__name__) for item in call] == [
        ((), "Call"),
        ((0,), "BinaryExpression"),
    ]

    producer_expression = _expression("p[x + 1] + p[x + 1]")
    without_producer = _detect_occurrences("out", producer_expression, {})
    with_producer = _detect_occurrences("out", producer_expression, {"p": object()})
    assert [item.path for item in without_producer if item.path in {(0, 0), (1, 0)}] == [
        (0, 0),
        (1, 0),
    ]
    assert [item.path for item in with_producer] == [(), (0, 0), (1, 0)]


def test_sum_bounds_remain_outside_the_new_binder_and_named_producers_are_skipped() -> None:
    expression = _expression("Sum(x + 1, (i, x + 1, x + 1))")

    occurrences = _detect_occurrences("out", expression, {"x": object()})

    assert [(item.path, item.binders) for item in occurrences] == [
        ((), ()),
        ((0,), ()),
        ((1,), ()),
        ((2,), ("i",)),
    ]


def test_candidate_deduplication_ignores_occurrence_discovery_routes() -> None:
    from py_science.formula.optimization import (
        _candidate_semantic_key,
        _CandidateComputation,
        _EvaluationScope,
        _Occurrence,
    )

    expression = _expression("x + 1")
    proposed = _expression("x")
    scope = _EvaluationScope((), (), ())
    occurrences = tuple(
        _Occurrence("expression", path, expression, frozenset({"x"}), (), scope)
        for path in ((0,), (1,))
    )
    candidates = tuple(
        _CandidateComputation(
            kind="horner",
            target="expression",
            original=expression,
            proposed=proposed,
            occurrences=(occurrence,),
        )
        for occurrence in occurrences
    )

    assert _candidate_semantic_key(candidates[0]) == _candidate_semantic_key(candidates[1])


def test_extraction_renderer_preserves_legacy_text_and_exhaustion_is_quiet() -> None:
    expression = _expression("x[i] + 1 + (x[i] + 1)")

    assert _extraction_opportunities("a", expression, {}) == (
        "equation a: extract repeated `x[i] + 1` (2 occurrences)",
    )
    assert _extraction_opportunities("a", _expression("x + 1"), {}) == ()
    with pytest.raises(_TraversalExhausted):
        _detect_occurrences("a", expression, {}, max_nodes=1)


def test_optimization_config_is_strict_and_bounded() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    default = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x")
    disabled = AnalysisRequest.model_validate(
        {
            "syntax": FormulaSyntax.SYMPY,
            "expression": "x",
            "optimization": {"max_suggestions": 0},
        }
    )
    assert default.optimization.max_suggestions == 3
    assert disabled.optimization.max_suggestions == 0
    with pytest.raises(ValidationError) as error:
        AnalysisRequest.model_validate(
            {
                "syntax": FormulaSyntax.SYMPY,
                "expression": "x",
                "optimization": {"max_suggestions": 17},
            }
        )
    assert error.value.errors()[0]["loc"] == ("optimization", "max_suggestions")


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


def test_optimization_suggestion_rejects_invalid_zero_or_negative_work() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from pydantic import ValidationError

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * y + x * z"))
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = outcome.optimization.suggestions[0]
    zero_post_work = type(suggestion).model_validate(
        {
            **suggestion.model_dump(),
            "objective_before": "1",
            "objective_after": "0",
            "objective_savings": "1",
        }
    )
    assert type(suggestion).model_validate_json(zero_post_work.model_dump_json()) == zero_post_work
    for invalid_work in (
        {"objective_before": "0", "objective_after": "0", "objective_savings": "0"},
        {"objective_before": "1", "objective_after": "-1", "objective_savings": "2"},
        {"objective_before": "1", "objective_after": "0", "objective_savings": "0"},
        {"objective_before": "1", "objective_after": "0", "objective_savings": "-1"},
        {"objective_before": "2", "objective_after": "0", "objective_savings": "1"},
    ):
        with pytest.raises(ValidationError):
            type(suggestion).model_validate({**suggestion.model_dump(), **invalid_work})


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


def test_disabled_optimization_preserves_every_ordinary_field() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    enabled = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1) * (x + 1)"))
    disabled = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1) * (x + 1)",
            optimization=OptimizationConfig(max_suggestions=0),
        )
    )
    assert enabled.status == "success" and disabled.status == "success"
    assert enabled.model_copy(update={"optimization": None}) == disabled.model_copy(
        update={"optimization": None}
    )
    assert disabled.optimization is not None
    assert disabled.optimization.status == "disabled"


def test_optimization_config_truth_table_and_exact_error_paths() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax
    from pydantic import ValidationError

    base = {"syntax": FormulaSyntax.SYMPY, "expression": "x"}
    assert AnalysisRequest.model_validate(base).optimization.max_suggestions == 3
    for accepted in (0, 16):
        assert (
            AnalysisRequest.model_validate(
                {**base, "optimization": {"max_suggestions": accepted}}
            ).optimization.max_suggestions
            == accepted
        )
    for rejected in (-1, 17, 1.5, "3"):
        with pytest.raises(ValidationError) as error:
            AnalysisRequest.model_validate({**base, "optimization": {"max_suggestions": rejected}})
        assert error.value.errors()[0]["loc"] == (
            "optimization",
            "max_suggestions",
        )
    with pytest.raises(ValidationError) as error:
        AnalysisRequest.model_validate(
            {**base, "optimization": {"max_suggestions": 3, "extra": True}}
        )
    assert error.value.errors()[0]["loc"] == ("optimization", "extra")


def test_report_and_suggestion_cross_field_truth_table() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationReport,
        OptimizationTarget,
        analyze,
    )
    from pydantic import ValidationError

    populated = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1) * (x + 1)",
        )
    )
    assert populated.status == "success" and populated.optimization is not None
    suggestion = populated.optimization.suggestions[0]
    assert OptimizationReport(requested_limit=3, status="complete").suggestions == ()
    assert OptimizationReport(
        requested_limit=3, status="complete", suggestions=(suggestion,)
    ).suggestions == (suggestion,)
    assert (
        OptimizationReport(
            requested_limit=3,
            status="incomplete",
            suggestions=(suggestion,),
            qualifications=("optimization candidate budget exhausted",),
        ).status
        == "incomplete"
    )
    for invalid in (
        {"requested_limit": 0, "status": "complete"},
        {"requested_limit": 3, "status": "disabled"},
        {"requested_limit": 3, "status": "incomplete"},
        {
            "requested_limit": 3,
            "status": "complete",
            "qualifications": ("unexpected qualification",),
        },
    ):
        with pytest.raises(ValidationError):
            OptimizationReport.model_validate(invalid)
    suggestion_data = suggestion.model_dump()
    transformation = suggestion.transformations[0]
    second_target = transformation.model_copy(
        update={"target": OptimizationTarget(kind="equation", name="other")}
    )
    for invalid in (
        {**suggestion_data, "transformations": ()},
        {**suggestion_data, "transformations": (transformation, transformation)},
        {**suggestion_data, "transformations": (transformation, second_target)},
        {**suggestion_data, "kind": "cross_equation_sharing"},
        {
            **suggestion_data,
            "target": transformation.target,
            "occurrences": transformation.occurrences,
            "original": transformation.original,
            "proposed": transformation.proposed,
        },
    ):
        with pytest.raises(ValidationError):
            type(suggestion).model_validate(invalid)
    schema = type(suggestion).model_json_schema()
    assert schema["properties"]["transformations"]["minItems"] == 1
    assert not ({"target", "occurrences", "original", "proposed"} & schema["properties"].keys())
    assert type(suggestion).model_validate_json(suggestion.model_dump_json()) == suggestion
    with pytest.raises(ValidationError):
        type(suggestion).model_validate({**suggestion_data, "savings": "-1"})
    with pytest.raises(ValidationError):
        type(suggestion).model_validate({**suggestion_data, "intermediate": None})
    with pytest.raises(ValidationError):
        type(suggestion).model_validate(
            {
                **suggestion_data,
                "conclusion": "proved_under_assumptions",
                "conditions": (),
                "assumptions_used": (),
            }
        )
    with pytest.raises(ValidationError):
        type(populated).model_validate({**populated.model_dump(), "optimization": None})


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


def test_advice_has_a_separate_result_allowance_and_excludes_its_key_from_base() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service

    assert formula_service.MAX_RESULT_BYTES == 262_144
    assert formula_service.MAX_OPTIMIZATION_BYTES == 262_144
    assert formula_service.MAX_COMBINED_RESULT_BYTES == 524_288
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    assert outcome.status == "success" and outcome.optimization is not None
    base_json = outcome.model_dump_json(exclude={"optimization"})
    assert '"optimization"' not in base_json
    assert len(outcome.optimization.model_dump_json().encode("utf-8")) < 65_536


def test_candidate_budget_exhaustion_preserves_already_proved_advice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import optimization as optimization_service

    monkeypatch.setattr(optimization_service, "MAX_OPTIMIZATION_CANDIDATES", 1)
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 0) * (y + 0)",
        )
    )
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.optimization.status == "incomplete"
    assert outcome.optimization.qualifications == (
        "optimization depth-one generated transitions budget exhausted (measured 2, configured 1)",
    )
    assert len(outcome.optimization.suggestions) == 1


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


def test_public_proposals_reparse_and_reconstruct_independently() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    for expression in (
        "(x + 1) * (x + 1)",
        "1/x + 1/x",
        "x*y + x*z",
        "(x + 0) * y",
        "Sum(x*x + i, (i, 0, 3))",
    ):
        outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))
        assert outcome.status == "success" and outcome.optimization is not None
        plan = outcome.optimization.plans[0]
        proposed = _expression(plan.trace[0].transformations[0].proposed.normalized_sympy)
        assert plan.trace[0].candidate.expression is not None
        candidate = _expression(plan.trace[0].candidate.expression)
        assert proposed == candidate
        replayed = analyze(AnalysisRequest.model_validate(plan.trace[0].candidate.model_dump()))
        assert replayed.status == "success"


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


def test_historical_exact_base_result_limit_still_succeeds() -> None:
    from py_science.formula import AnalysisSuccess
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation, OperationCounts, ScenarioResult

    def outcome_with_padding(length: int) -> AnalysisSuccess:
        return AnalysisSuccess(
            interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
            operation_counts=OperationCounts(
                additions=0,
                subtractions=0,
                multiplications=0,
                divisions=0,
                powers=0,
            ),
            abstract_work=0,
            scenarios=(
                ScenarioResult(
                    name="padding",
                    substituted_work="0",
                    qualifications=("x" * length,),
                ),
            ),
        )

    empty = outcome_with_padding(0)
    overhead = len(empty.model_dump_json(exclude={"optimization"}).encode("utf-8"))
    exact = outcome_with_padding(formula_service.MAX_RESULT_BYTES - overhead)
    assert (
        len(exact.model_dump_json(exclude={"optimization"}).encode("utf-8"))
        == formula_service.MAX_RESULT_BYTES
    )
    assert formula_service._bound_result(exact).status == "success"  # pyright: ignore[reportPrivateUsage]
    overflow = outcome_with_padding(formula_service.MAX_RESULT_BYTES - overhead + 1)
    assert formula_service._bound_result(overflow).status == "failure"  # pyright: ignore[reportPrivateUsage]


def test_oversized_advice_truncates_without_replacing_base_success() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = outcome.optimization.suggestions[0]
    oversized = suggestion.model_copy(
        update={
            "transformations": (
                suggestion.transformations[0].model_copy(
                    update={
                        "proposed": Interpretation(
                            normalized_sympy="x" * 140_000, normalized_latex="x" * 140_000
                        )
                    }
                ),
            )
        }
    )
    bounded = formula_service._bound_result(  # pyright: ignore[reportPrivateUsage]
        outcome.model_copy(
            update={
                "optimization": outcome.optimization.model_copy(
                    update={"suggestions": (oversized,)}
                )
            }
        )
    )
    assert bounded.status == "success"
    assert bounded.optimization.status == outcome.optimization.status
    assert bounded.optimization.suggestions == ()
    assert bounded.optimization.projection_status == "truncated"
    assert bounded.optimization.projection_qualifications[0].startswith(
        "optimization advice bytes budget exhausted (measured "
    )
    assert "configured 262144" in bounded.optimization.projection_qualifications[0]


def test_exact_base_and_maximum_field_contribution_preserve_success() -> None:
    from py_science.formula import AnalysisSuccess
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation, OperationCounts, ScenarioResult

    empty = AnalysisSuccess(
        interpretation=Interpretation(normalized_sympy="x", normalized_latex="x"),
        operation_counts=OperationCounts(),
        abstract_work=0,
        scenarios=(ScenarioResult(name="padding", substituted_work="0", qualifications=("",)),),
    )
    base_overhead = len(empty.model_dump_json(exclude={"optimization"}).encode("utf-8"))
    exact_base = empty.model_copy(
        update={
            "scenarios": (
                empty.scenarios[0].model_copy(
                    update={
                        "qualifications": (
                            "x" * (formula_service.MAX_RESULT_BYTES - base_overhead),
                        )
                    }
                ),
            )
        }
    )
    assert (
        len(exact_base.model_dump_json(exclude={"optimization"}).encode("utf-8"))
        == formula_service.MAX_RESULT_BYTES
    )

    seed = exact_base.optimization.model_copy(
        update={"status": "incomplete", "qualifications": ("",)}
    )
    seed_bytes = len(seed.model_dump_json().encode("utf-8"))
    maximum_report = seed.model_copy(
        update={"qualifications": ("y" * (formula_service.MAX_OPTIMIZATION_BYTES - seed_bytes),)}
    )
    assert (
        len(maximum_report.model_dump_json().encode("utf-8"))
        == formula_service.MAX_OPTIMIZATION_BYTES
    )
    combined = exact_base.model_copy(update={"optimization": maximum_report})
    field_contribution = len(combined.model_dump_json().encode("utf-8")) - len(
        combined.model_dump_json(exclude={"optimization"}).encode("utf-8")
    )
    assert field_contribution > formula_service.MAX_OPTIMIZATION_BYTES

    bounded = formula_service._bound_result(combined)  # pyright: ignore[reportPrivateUsage]
    assert bounded.status == "success"
    assert bounded.optimization.status == "incomplete"
    assert bounded.optimization.qualifications == (
        "optimization search qualifications truncated by output projection",
    )
    assert bounded.optimization.projection_status == "truncated"
    assert bounded.optimization.projection_qualifications == (
        "optimization advice bytes budget exhausted",
    )


def test_unexpected_reasoning_and_verifier_defects_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import optimization as optimization_service

    def defect(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unexpected optimization defect")

    monkeypatch.setattr(optimization_service.ReasoningContext, "build", defect)
    result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    assert result.status == "success"
    assert result.optimization.status == "failed"

    monkeypatch.undo()
    monkeypatch.setattr(optimization_service, "_verify_candidate", defect)
    result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    assert result.status == "success"
    assert result.optimization.status == "failed"


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


def test_independent_budget_qualifications_report_measured_and_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import optimization as optimization_service

    monkeypatch.setattr(optimization_service, "MAX_OPTIMIZATION_CANDIDATES", 1)
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)"))
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.optimization.status == "incomplete"
    qualification = outcome.optimization.qualifications[0]
    assert "generated transitions" in qualification
    assert "measured 2" in qualification
    assert "configured 1" in qualification
    assert outcome.optimization.suggestions


def test_cross_equation_canonical_binders_do_not_capture_user_symbols() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        OptimizationConfig,
        VariableDeclaration,
        analyze,
    )

    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="bound", expression="Eq(bound, Sum(i, (i, 0, 3)))"),
                EquationRequest(
                    name="free",
                    expression="Eq(free, Sum(optimization_sum_0, (i, 0, 3)))",
                ),
            ),
            variables={"optimization_sum_0": VariableDeclaration(domain=MathematicalDomain.REAL)},
            optimization=OptimizationConfig(max_suggestions=16),
        )
    )

    assert outcome.status == "success"
    assert all(item.kind != "cross_equation_sharing" for item in outcome.optimization.suggestions)


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


def test_cross_equation_domain_signature_overflow_is_a_typed_incomplete_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        VariableDeclaration,
        analyze,
    )
    from py_science.formula import optimization as optimization_service
    from py_science.formula.expressions import ExpressionTooComplex

    def exhausted(*_args: object, **_kwargs: object) -> object:
        raise ExpressionTooComplex("bounded substitution exhausted")

    monkeypatch.setattr(optimization_service, "substitute", exhausted)
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="left",
                    expression="Eq(left[i], x[i] + 1)",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
                EquationRequest(
                    name="right",
                    expression="Eq(right[j], x[j] - 1)",
                    domains={"j": IndexDomain(lower="0", upper="N")},
                ),
            ),
            variables={
                "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
        )
    )

    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.optimization.status == "incomplete"
    assert any(
        "optimization per-candidate transformation nodes budget exhausted" in item
        for item in outcome.optimization.qualifications
    )


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


def test_recursive_horner_inspection_is_charged_before_backend_descent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import optimization as optimization_service
    from py_science.formula.expressions import expression_node_count

    expression = "2*x**3 + 3*x**2 + 4*x + 5"
    initial_nodes = expression_node_count(_expression(expression))
    monkeypatch.setattr(optimization_service, "MAX_OPTIMIZATION_INSPECTIONS", initial_nodes)

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression))

    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.interpretation.normalized_sympy == "4*x + 5 + 3*x**2 + 2*x**3"
    assert outcome.optimization.status == "incomplete"
    assert any(
        item
        == (
            "optimization depth-one inspected nodes budget exhausted "
            f"(measured {initial_nodes * 2}, configured {initial_nodes})"
        )
        for item in outcome.optimization.qualifications
    )


@pytest.mark.parametrize(
    ("constant", "configured", "resource"),
    [
        ("MAX_OPTIMIZATION_INSPECTIONS", 1, "inspected nodes"),
        ("MAX_OPTIMIZATION_TRANSFORM_NODES", 1, "transformation nodes"),
        ("MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES", 1, "aggregate transformation nodes"),
        ("MAX_OPTIMIZATION_PROOFS", 0, "proof steps"),
        ("MAX_OPTIMIZATION_PROOF_NODES", 1, "proof nodes"),
        ("MAX_OPTIMIZATION_WORK_NODES", 1, "work-comparison nodes"),
    ],
)
def test_each_independent_search_budget_preserves_base_success(
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    configured: int,
    resource: str,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import optimization as optimization_service

    monkeypatch.setattr(optimization_service, constant, configured)
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 0) * (y + 0)"))
    assert outcome.status == "success" and outcome.optimization is not None
    assert outcome.interpretation.normalized_sympy == "x*y"
    assert outcome.optimization.status == "incomplete"
    assert any(resource in item for item in outcome.optimization.qualifications)
    assert all(
        "measured" in item and "configured" in item for item in outcome.optimization.qualifications
    )


def test_limits_and_repeated_process_json_are_deterministic() -> None:
    import subprocess
    import sys

    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizationConfig,
        analyze,
    )

    expression = "(a*x**3 + b*x**2 + c*x + d) + (y + 1)*(y + 1) + z*w + z*q + (r + 0)"
    for limit in (0, 1, 3, 16):
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=expression,
                optimization=OptimizationConfig(max_suggestions=limit),
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        assert len(outcome.optimization.suggestions) <= limit
        assert outcome.optimization.status == ("disabled" if limit == 0 else "incomplete")

    empty = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    assert empty.status == "success" and empty.optimization is not None
    assert empty.optimization.status == "complete"
    assert empty.optimization.suggestions == ()
    assert empty.optimization.qualifications == ()

    script = f"""
from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze
request = AnalysisRequest(
    syntax=FormulaSyntax.SYMPY,
    expression={expression!r},
    optimization=OptimizationConfig(max_suggestions=16),
)
print(analyze(request).model_dump_json())
"""
    populations = tuple(
        subprocess.check_output([sys.executable, "-c", script], text=True).strip() for _ in range(3)
    )
    assert populations[0] == populations[1] == populations[2]


def test_multibyte_advice_limit_measures_encoded_bytes() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula import service as formula_service
    from py_science.formula.models import Interpretation

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))
    assert outcome.status == "success" and outcome.optimization is not None
    suggestion = outcome.optimization.suggestions[0]
    oversized = suggestion.model_copy(
        update={
            "transformations": (
                suggestion.transformations[0].model_copy(
                    update={
                        "proposed": Interpretation(
                            normalized_sympy="é" * 140_000, normalized_latex="é" * 140_000
                        )
                    }
                ),
            )
        }
    )
    bounded = formula_service._bound_result(  # pyright: ignore[reportPrivateUsage]
        outcome.model_copy(
            update={
                "optimization": outcome.optimization.model_copy(
                    update={"suggestions": (oversized,)}
                )
            }
        )
    )
    assert bounded.status == "success" and bounded.optimization is not None
    assert bounded.optimization.projection_status == "truncated"
    qualification = bounded.optimization.projection_qualifications[0]
    assert "advice bytes" in qualification
    assert "measured" in qualification and "configured 262144" in qualification


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


def test_retained_analysis_disables_optimization() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula.service import _analyze_computation

    retained = _analyze_computation(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))

    assert not isinstance(retained, AnalysisFailure)
    assert retained.success.optimization.model_dump() == {
        "requested_limit": 0,
        "status": "disabled",
        "suggestions": (),
        "plans": (),
        "qualifications": (),
        "projection_status": "complete",
        "projection_qualifications": (),
    }
    assert (
        type(retained.success).model_validate_json(retained.success.model_dump_json()).optimization
        == retained.success.optimization
    )


def test_complete_candidate_replays_expression_local_reuse_and_neutral_removal() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula.optimization import (
        _complete_candidate,
        _generate_candidates,
        _OptimizationBudget,
    )
    from py_science.formula.service import _analyze_computation

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1) * (x + 1) + 0",
    )
    retained = _analyze_computation(request)
    assert not isinstance(retained, AnalysisFailure)
    candidates, _ = _generate_candidates(retained, _OptimizationBudget())
    for candidate in candidates:
        if candidate.kind not in {"repeated_subexpression", "redundant_operation_removal"}:
            continue
        replayed = _analyze_computation(_complete_candidate(candidate, request, retained))
        assert not isinstance(replayed, AnalysisFailure)
        assert replayed.expression is not None
        assert replayed.aggregate_analysis.total_work != retained.aggregate_analysis.total_work


def test_complete_candidate_proof_reads_the_replayed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import py_science.formula.optimization as optimization_service
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula.computation import RetainedComputation
    from py_science.formula.optimization import _CandidateComputation

    original_complete_candidate = optimization_service._complete_candidate

    def falsified_complete_candidate(
        candidate: _CandidateComputation,
        request: AnalysisRequest,
        computed: RetainedComputation,
    ) -> AnalysisRequest:
        complete = original_complete_candidate(candidate, request, computed)
        return AnalysisRequest.model_validate(
            {**complete.model_dump(mode="python"), "expression": "0"}
        )

    monkeypatch.setattr(optimization_service, "_complete_candidate", falsified_complete_candidate)

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x*y + x*z"))

    assert outcome.status == "success"
    assert all(item.kind != "factoring" for item in outcome.optimization.suggestions)


def test_complete_candidate_schedule_preserves_all_kinds_and_the_tail() -> None:
    from py_science.formula.optimization import (
        _CandidateComputation,
        _complete_candidate_schedule,
    )

    kinds = (
        "repeated_subexpression",
        "repeated_call",
        "reciprocal_reuse",
        "factoring",
        "redundant_operation_removal",
        "iterator_invariant_hoisting",
        "cross_equation_sharing",
        "horner",
        "repeated_subexpression",
    )
    candidates = tuple(
        _CandidateComputation(
            kind=kind,
            target=f"target{position}",
            original=_expression("x"),
            proposed=_expression("x"),
            occurrences=(),
        )
        for position, kind in enumerate(kinds)
    )

    scheduled = _complete_candidate_schedule(candidates)

    assert len(scheduled) == 8
    assert {item.kind for item in scheduled} == set(kinds)
    assert scheduled[-1] is candidates[-1]


def test_ordinary_analysis_optimization_ownership() -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    default = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))
    disabled = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x + 0",
            optimization=OptimizationConfig(max_suggestions=0),
        )
    )

    assert default.status == "success"
    assert default.optimization.requested_limit == 3
    assert default.optimization.status == "complete"
    assert any(
        suggestion.kind == "redundant_operation_removal"
        for suggestion in default.optimization.suggestions
    )
    assert disabled.status == "success"
    assert disabled.optimization.model_dump() == {
        "requested_limit": 0,
        "status": "disabled",
        "suggestions": (),
        "plans": (),
        "qualifications": (),
        "projection_status": "complete",
        "projection_qualifications": (),
    }


def test_optimize_operation_returns_replayable_complete_plans() -> None:
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        OptimizeRequest,
        analyze,
        optimize,
    )

    request = OptimizeRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="x*x + x*x",
    )
    result = optimize(request)

    assert result.status == "success"
    assert result.requested_limit == 3
    assert result.plans
    plan = result.plans[0]
    assert plan.candidate.syntax == FormulaSyntax.SYMPY
    assert plan.candidate.expression is not None
    assert plan.candidate.outputs == ("expression",)
    replay = analyze(AnalysisRequest.model_validate(plan.candidate.model_dump()))
    assert replay.status == "success"


def test_analysis_replay_rejects_invalid_output_identities() -> None:
    from py_science.formula import AnalysisRequest, EquationRequest, FormulaSyntax
    from pydantic import ValidationError

    equation = EquationRequest(name="a", expression="Eq(a, x)")
    payloads = (
        {"syntax": FormulaSyntax.SYMPY, "expression": "x", "outputs": ("wrong",)},
        {
            "syntax": FormulaSyntax.SYMPY,
            "equations": (equation,),
            "outputs": ("missing",),
        },
        {
            "syntax": FormulaSyntax.SYMPY,
            "equations": (equation,),
            "outputs": ("a", "a"),
        },
    )
    for payload in payloads:
        with pytest.raises(ValidationError, match="output identit"):
            AnalysisRequest.model_validate(payload)


def test_optimize_system_plan_outputs_exclude_generated_producers() -> None:
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        OptimizationSuccess,
        OptimizeRequest,
        VariableDeclaration,
        analyze,
        optimize,
    )

    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="a", expression="Eq(a, x*x + 1)"),
                EquationRequest(name="b", expression="Eq(b, x*x - 1)"),
            ),
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            max_plans=16,
        )
    )

    assert isinstance(result, OptimizationSuccess)
    sharing = next(
        plan for plan in result.plans if plan.suggestion.kind == "cross_equation_sharing"
    )
    assert sharing.candidate.outputs == ("a", "b")
    assert {equation.name for equation in sharing.candidate.equations} == {
        "optimization_tmp_1",
        "a",
        "b",
    }
    replay = analyze(AnalysisRequest.model_validate(sharing.candidate.model_dump()))
    assert replay.status == "success"


def test_optimize_result_bound_keeps_every_plan_that_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        FormulaSyntax,
        OptimizationSuccess,
        OptimizeRequest,
        optimize,
        service,
    )

    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(alpha + beta)*(alpha + beta) + 0",
            max_plans=16,
        )
    )
    assert isinstance(result, OptimizationSuccess)
    assert len(result.plans) >= 2
    oversized = result.model_copy(
        update={"search_status": "incomplete", "qualifications": ("x" * 10_000,)}
    )
    monkeypatch.setattr(service, "MAX_OPTIMIZATION_BYTES", 30_000)

    bounded = service._bound_optimization_result(oversized)

    assert bounded.search_status == "incomplete"
    assert bounded.projection_status == "complete"
    assert len(bounded.plans) == len(result.plans)
    assert len(bounded.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_optimize_result_bound_keeps_largest_fitting_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        FormulaSyntax,
        OptimizationSuccess,
        OptimizeRequest,
        optimize,
        service,
    )

    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(alpha + beta)*(alpha + beta) + 0",
            max_plans=16,
        )
    )
    assert isinstance(result, OptimizationSuccess)
    assert len(result.plans) >= 2
    oversized = result.model_copy(
        update={"search_status": "incomplete", "qualifications": ("x" * 10_000,)}
    )
    monkeypatch.setattr(service, "MAX_OPTIMIZATION_BYTES", 12_000)

    bounded = service._bound_optimization_result(oversized)

    assert bounded.projection_status == "truncated"
    assert len(bounded.plans) < len(result.plans)
    assert len(bounded.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_optimize_result_bound_handles_oversized_empty_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import OptimizationSuccess, service

    oversized = OptimizationSuccess(
        requested_limit=3,
        search_status="incomplete",
        qualifications=("x" * 4_000,),
    )
    monkeypatch.setattr(service, "MAX_OPTIMIZATION_BYTES", 5_000)

    bounded = service._bound_optimization_result(oversized)

    assert bounded.plans == ()
    assert bounded.search_status == "incomplete"
    assert len(bounded.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


def test_optimize_operation_bounds_duplicated_plan_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import (
        FormulaSyntax,
        OptimizationSuccess,
        OptimizeRequest,
        optimize,
        service,
    )

    monkeypatch.setattr(service, "MAX_OPTIMIZATION_BYTES", 600)
    result = optimize(
        OptimizeRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(alpha + beta)*(alpha + beta) + 0",
            max_plans=16,
        )
    )

    assert isinstance(result, OptimizationSuccess)
    assert result.search_status == "complete"
    assert result.projection_status == "truncated"
    assert result.projection_qualifications
    assert len(result.model_dump_json().encode("utf-8")) <= service.MAX_OPTIMIZATION_BYTES


# Objective-v1 regressions deliberately define the public optimizer-only boundary.
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

    import py_science.formula.optimization as optimization
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
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

    monkeypatch.setattr(optimization, "compare_aggregate_work", qualified_relation)
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


def test_composed_search_v1_emits_replayable_trace() -> None:
    """A composed plan is represented by replayable parent-relative steps."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0"))
    assert outcome.status == "success"
    # Protocol v15 replaces the former single-family suggestion payload.
    assert any(len(plan.trace) == 2 for plan in outcome.optimization.plans)


def test_composed_search_v1_budget_seams_distinguish_transition_and_final_proofs() -> None:
    """The injected counters qualify the owning search phase, not a generic budget."""
    from dataclasses import replace

    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula.optimization import (
        _generate_candidate_lanes,
        _optimization_report,
        _OptimizationBudget,
        _OptimizationBudgetConfig,
        _RetainedLaneCollector,
    )
    from py_science.formula.service import _analyze_computation

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0"
    )
    computed = _analyze_computation(request)
    assert not isinstance(computed, AnalysisFailure)
    materialization_budget = _OptimizationBudget(
        replace(_OptimizationBudgetConfig(), candidates=1), "depth-one"
    )
    collector = _RetainedLaneCollector(materialization_budget)
    lanes, qualifications = _generate_candidate_lanes(
        computed, materialization_budget, collector
    )
    assert sum(map(len, lanes.values())) == collector.retained_count == 1
    # The transition allowance is consumed at proposal materialization, not
    # later when the fair scheduler projects already-generated proposals.
    assert materialization_budget.candidates == 1
    assert qualifications == (
        "optimization depth-one generated transitions budget exhausted "
        "(measured 2, configured 1)",
    )
    collector.schedule()
    assert materialization_budget.candidates == 1
    assert collector.exhaustion() is None

    transition = _optimization_report(
        request,
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), proofs=0),
    )
    final = _optimization_report(
        request,
        computed,
        computed.work_context,
        replace(_OptimizationBudgetConfig(), final_proofs=0),
    )

    assert transition.status == final.status == "incomplete"
    assert transition.qualifications == (
        "optimization depth-one proof steps budget exhausted (measured 1, configured 0)",
    )
    assert final.qualifications == (
        "optimization final-acceptance proof steps budget exhausted (measured 1, configured 0)",
    )


def test_composed_search_v1_max_plans_is_an_exact_ranked_prefix() -> None:
    """Changing the output limit neither changes nor reruns the search population."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    def plans(limit: int):
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="(x + 1)*(x + 1) + 0",
                optimization=OptimizationConfig(max_suggestions=limit),
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        return outcome.optimization.plans

    full = plans(16)
    assert len(full) >= 2
    assert plans(1) == full[:1]
    assert plans(2) == full[:2]


def test_composed_search_v1_trace_objectives_are_continuous_and_replayable() -> None:
    """Every local transition connects its parent objective to the final proof."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0"))
    assert outcome.status == "success" and outcome.optimization is not None
    plan = next(item for item in outcome.optimization.plans if len(item.trace) == 2)

    assert plan.trace[0].objective_before == plan.suggestion.objective_before
    assert plan.trace[-1].objective_after == plan.suggestion.objective_after
    assert plan.trace[0].objective_after == plan.trace[1].objective_before
    assert plan.trace[-1].candidate == plan.candidate
    for step in plan.trace:
        replayed = analyze(AnalysisRequest.model_validate(step.candidate.model_dump()))
        assert replayed.status == "success"


def test_composed_search_v1_alpha_renamed_binders_keep_population_order() -> None:
    """Search-only canonicalization makes alpha-equivalent binders rank identically."""
    from py_science.formula import AnalysisRequest, FormulaSyntax, OptimizationConfig, analyze

    def population(index: str) -> list[tuple[tuple[str, ...], str]]:
        outcome = analyze(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=f"Sum((x + 1)*(x + 1), ({index}, 0, 3))",
                optimization=OptimizationConfig(max_suggestions=16),
            )
        )
        assert outcome.status == "success" and outcome.optimization is not None
        return [
            (tuple(step.kind for step in plan.trace), plan.suggestion.objective_savings)
            for plan in outcome.optimization.plans
        ]

    assert population("i") == population("j")


def test_composed_search_v1_retained_lanes_are_round_robin_and_order_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bounded depth population is independent of family and emission order."""
    from dataclasses import replace

    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula import optimization as optimization_service
    from py_science.formula.optimization import (
        _CandidateComputation,
        _optimization_report,
        _OptimizationBudget,
        _OptimizationBudgetConfig,
        _proposal_sort_key,
        _RetainedLaneCollector,
        _round_robin_candidates,
    )
    from py_science.formula.service import _analyze_computation

    families = tuple(reversed(optimization_service._FAMILY_ORDER[:3]))

    def proposal(kind: str, value: int) -> _CandidateComputation:
        expression = _expression(f"x + {value}")
        return _CandidateComputation(
            kind=cast("object", kind),  # type: ignore[arg-type]
            target="expression",
            original=expression,
            proposed=_expression("x"),
            occurrences=(),
        )

    population = {
        family: tuple(proposal(family, value) for value in range(4)) for family in families
    }
    budget = _OptimizationBudget(replace(_OptimizationBudgetConfig(), candidates=12))
    collector = _RetainedLaneCollector(budget)
    # Reverse both family registration and each lane's generator emission.
    for family in reversed(families):
        for candidate in reversed(population[family]):
            collector.add((family,), candidate)
            assert collector.retained_count <= 12
    expected = _round_robin_candidates(
        (
            ((family,), tuple(sorted(candidates, key=_proposal_sort_key)))
            for family, candidates in population.items()
        ),
        _OptimizationBudget(),
    )
    retained = collector.schedule()
    assert retained == expected
    assert budget.candidates == 12
    assert collector.retained_count == 12
    assert collector.exhaustion() is None

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + (y + 0)")
    computed = _analyze_computation(request)
    assert not isinstance(computed, AnalysisFailure)
    seam = replace(_OptimizationBudgetConfig(), candidates=2, complete_reanalyses=2)
    baseline = _optimization_report(request, computed, computed.work_context, seam)
    monkeypatch.setattr(
        optimization_service, "_FAMILY_ORDER", tuple(reversed(optimization_service._FAMILY_ORDER))
    )
    reversed_families = _optimization_report(request, computed, computed.work_context, seam)
    assert reversed_families == baseline
