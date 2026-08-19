from typing import Any

import py_science.formula.dominance as dominance_policy
import py_science.formula.service as formula_service
import pytest
from py_science.formula import (
    AnalysisFailure,
    Assumption,
    DirectedDefinition,
    DominanceAnalysisRequest,
    DominanceAnalysisSuccess,
    DominanceRange,
    FormulaSyntax,
    MathematicalDomain,
    PrimitiveCost,
    VariableDeclaration,
    analyze,
    analyze_dominance,
)
from py_science.formula.sign_chart import ChartRefusal, ExplicitAxis, StructuralSignChart
from pydantic import ValidationError


def _request(
    work: str,
    domain: MathematicalDomain = MathematicalDomain.POSITIVE_INTEGER,
    **changes: object,
) -> DominanceAnalysisRequest:
    request = DominanceAnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="cost(N)",
        axis="N",
        variables={"N": VariableDeclaration(domain=domain)},
        primitive_costs=(PrimitiveCost(name="cost", parameters=("N",), work=work),),
    )
    return request.model_copy(update=changes)


def _success(request: DominanceAnalysisRequest) -> DominanceAnalysisSuccess:
    result = analyze_dominance(request)
    assert isinstance(result, DominanceAnalysisSuccess)
    return result


def test_integer_correction_contract_and_pair_signs() -> None:
    result = _success(_request("N**2 - N + 1"))
    assert result.kind == "dominance_analysis"
    assert result.axis_domain == MathematicalDomain.POSITIVE_INTEGER
    assert [(term.id, term.coefficient) for term in result.terms] == [
        ("power:2", "1"),
        ("power:1", "-1"),
        ("power:0", "1"),
    ]
    assert result.cells[0].model_dump() == {
        "kind": "integer_point",
        "value": "1",
        "dominant": ("power:2", "power:1", "power:0"),
        "blockers": (),
    }
    assert all(item.sign is not None for item in result.evidence)
    assert tuple(item.pair for item in result.evidence) == (
        ("power:2", "power:1"),
        ("power:2", "power:0"),
        ("power:1", "power:0"),
    )


def test_equivalent_spellings_have_identical_decomposition_and_regions() -> None:
    expanded = _success(_request("N**2 + 2*N + 1", MathematicalDomain.REAL))
    factored = _success(_request("(N + 1)**2", MathematicalDomain.REAL))
    assert expanded.terms == factored.terms
    assert expanded.shared_denominator == factored.shared_denominator
    assert expanded.cells == factored.cells
    assert expanded.exclusions == factored.exclusions


def test_cancelled_original_denominator_is_retained_as_an_exclusion() -> None:
    result = _success(_request("(N**2 - 1) / (N - 1)", MathematicalDomain.REAL))
    assert result.shared_denominator == "1"
    assert [item.value for item in result.exclusions] == ["1"]
    assert result.conditions == ("N != 1",)
    assert all(
        not (
            getattr(cell, "lower", None) == "1"
            and getattr(cell, "lower_inclusive", False)
        )
        and not (
            getattr(cell, "upper", None) == "1"
            and getattr(cell, "upper_inclusive", False)
        )
        for cell in result.cells
    )


def test_real_endpoints_and_integer_lattice_are_exact() -> None:
    real = _success(
        _request(
            "N**2 - N + 1",
            MathematicalDomain.REAL,
            range=DominanceRange(
                lower="0", upper="2", lower_inclusive=False, upper_inclusive=True
            ),
        )
    )
    integer = _success(_request("N**2 - N + 1", MathematicalDomain.INTEGER))
    assert real.effective_range == DominanceRange(
        lower="0", upper="2", lower_inclusive=False, upper_inclusive=True
    )
    assert getattr(real.cells[-1], "upper", None) == "2"
    assert getattr(real.cells[-1], "upper_inclusive", False) is True
    assert all("1000000000" not in cell.model_dump_json() for cell in integer.cells)
    assert all(cell.kind.startswith("integer") for cell in integer.cells)


def test_empty_integer_intersection_and_zero_work_have_distinct_statuses() -> None:
    empty = _success(
        _request(
            "N",
            MathematicalDomain.INTEGER,
            range=DominanceRange(
                lower="1/2",
                upper="3/4",
                lower_inclusive=True,
                upper_inclusive=True,
            ),
        )
    )
    zero = _success(_request("0", MathematicalDomain.REAL))
    assert empty.dominance_status == "empty"
    assert empty.effective_range is None
    assert empty.terms == empty.cells == ()
    assert zero.dominance_status == "complete"
    assert zero.effective_range is not None
    assert zero.terms == zero.cells == ()
    assert zero.shared_denominator == "1"
    assert zero.conditions == ("aggregate work is identically zero",)


def test_fixed_specialization_and_axis_assumption_provenance() -> None:
    request = DominanceAnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="cost(N, a)",
        axis="N",
        fixed={"a": "2"},
        variables={
            "N": VariableDeclaration(domain=MathematicalDomain.REAL),
            "a": VariableDeclaration(domain=MathematicalDomain.POSITIVE_REAL),
        },
        primitive_costs=(
            PrimitiveCost(name="cost", parameters=("N", "a"), work="a*N**2 + N"),
        ),
        assumptions=(
            Assumption(name="positive_N", relationship="N > 0"),
        ),
    )
    result = _success(request)
    assert [(term.id, term.coefficient) for term in result.terms] == [
        ("power:2", "2"),
        ("power:1", "1"),
    ]
    assert result.fixed == {"a": "2"}
    assert result.effective_range == DominanceRange(
        lower="0", upper="oo", lower_inclusive=False, upper_inclusive=False
    )
    assert tuple(item.name for item in result.assumptions_used) == ("positive_N",)


def test_request_rejects_invalid_axis_fixed_values_and_surplus_keys() -> None:
    base = _request("N")
    with pytest.raises(ValidationError, match="axis cannot be fixed"):
        DominanceAnalysisRequest.model_validate(
            {**base.model_dump(), "fixed": {"N": "1"}}
        )
    with pytest.raises(ValidationError, match=r"fixed\.x"):
        DominanceAnalysisRequest.model_validate(
            {
                **base.model_dump(),
                "variables": {
                    "N": base.variables["N"],
                    "x": VariableDeclaration(domain=MathematicalDomain.INTEGER),
                },
                "fixed": {"x": "1/2"},
            }
        )
    with pytest.raises(ValidationError, match="conflict with definitions"):
        DominanceAnalysisRequest.model_validate(
            {
                **base.model_dump(),
                "variables": {
                    "N": base.variables["N"],
                    "x": VariableDeclaration(domain=MathematicalDomain.REAL),
                },
                "fixed": {"x": "1"},
                "definitions": (DirectedDefinition(variable="x", expression="2"),),
            }
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        DominanceAnalysisRequest.model_validate({**base.model_dump(), "queries": ()})


def test_unknown_unsupported_and_nonfinite_work_abstain() -> None:
    unknown = DominanceAnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="opaque(N)",
        axis="N",
        variables={"N": VariableDeclaration(domain=MathematicalDomain.REAL)},
    )
    assert _success(unknown).blockers == (
        "aggregate work contains unknown primitive costs",
    )
    assert _success(_request("2**N", MathematicalDomain.REAL)).dominance_status == (
        "unresolved"
    )
    nonfinite = analyze_dominance(_request("oo", MathematicalDomain.REAL))
    assert isinstance(nonfinite, AnalysisFailure)


def test_result_models_reject_bad_truth_tables_and_correlations() -> None:
    integer = _success(_request("N**2 - N + 1"))
    payload = integer.model_dump()
    with pytest.raises(ValidationError, match="cell kind must match"):
        DominanceAnalysisSuccess.model_validate(
            {**payload, "axis_domain": MathematicalDomain.REAL}
        )
    with pytest.raises(ValidationError, match="requires every pair"):
        DominanceAnalysisSuccess.model_validate({**payload, "evidence": ()})
    with pytest.raises(ValidationError, match="proved complement"):
        DominanceAnalysisSuccess.model_validate({**payload, "never_dominant": ("power:0",)})
    with pytest.raises(ValidationError, match="empty dominance has no effective range"):
        DominanceAnalysisSuccess.model_validate(
            {
                **payload,
                "dominance_status": "empty",
                "cells": (),
                "terms": (),
                "evidence": (),
                "never_dominant": (),
                "exclusions": (),
                "blockers": (),
            }
        )


def test_every_dominance_budget_has_a_deterministic_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = (
        ("MAX_DOMINANCE_TERMS", 2, "dominance term bound exceeded"),
        ("MAX_DOMINANCE_PAIRS", 1, "dominance pair bound exceeded"),
        ("MAX_DOMINANCE_POINTS", 1, "dominance partition-point bound exceeded"),
        ("MAX_DOMINANCE_CELLS", 1, "dominance cell bound exceeded"),
        ("MAX_DOMINANCE_REASONING_STEPS", 2, "dominance reasoning-step bound exceeded"),
        ("MAX_DOMINANCE_INTERMEDIATE_NODES", 1, "dominance intermediate-node bound exceeded"),
        ("MAX_DOMINANCE_RENDER_BYTES", 1, "dominance rendering bound exceeded"),
        ("MAX_DOMINANCE_SUPPLEMENT_BYTES", 1, "dominance supplement bound exceeded"),
    )
    for name, limit, blocker in cases:
        with monkeypatch.context() as patch:
            patch.setattr(dominance_policy, name, limit)
            result = _success(_request("N**2 - N + 1", MathematicalDomain.REAL))
        assert result.dominance_status == "unresolved", name
        assert result.terms == result.cells == (), name
        assert result.blockers == (blocker,), name


def test_combined_result_overflow_is_an_analysis_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(formula_service, "MAX_RESULT_BYTES", 1)
    result = analyze_dominance(_request("N**2 - N + 1"))
    assert isinstance(result, AnalysisFailure)
    assert "dominance result exceeds" in result.error.message


def test_reconstruction_pair_and_backend_failures_are_falsifiable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_reconstruction(*_args: Any) -> bool:
        return False

    with monkeypatch.context() as patch:
        patch.setattr(dominance_policy, "_reconstructs", fail_reconstruction)
        reconstruction = _success(_request("N**2 - N + 1"))
    assert reconstruction.blockers == ("dominance reconstruction failed",)

    real_chart = dominance_policy.explicit_axis_sign_chart
    calls = 0

    def refuse_pair(*args: Any, **kwargs: Any) -> StructuralSignChart:
        nonlocal calls
        calls += 1
        if calls <= 2:
            return real_chart(*args, **kwargs)
        axis = args[2]
        assert isinstance(axis, ExplicitAxis)
        return StructuralSignChart(
            axis, (), (), (), (), (), ChartRefusal("forced pair-sign failure")
        )

    with monkeypatch.context() as patch:
        patch.setattr(dominance_policy, "explicit_axis_sign_chart", refuse_pair)
        pair = _success(_request("N**2 - N + 1"))
    assert pair.dominance_status == "unresolved"
    assert pair.blockers == ()
    assert pair.cells
    assert all(cell.blockers == ("forced pair-sign failure",) for cell in pair.cells)

    def fail_backend(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("boom")

    with monkeypatch.context() as patch:
        patch.setattr(dominance_policy, "dominance_rational_form", fail_backend)
        backend = _success(_request("N**2 - N + 1"))
    assert backend.blockers == ("aggregate work rational backend failed",)


def test_nested_analysis_is_the_independent_ordinary_analysis() -> None:
    request = _request("N**2 - N + 1")
    result = _success(request)
    assert result.analysis == analyze(request.analysis_request())
