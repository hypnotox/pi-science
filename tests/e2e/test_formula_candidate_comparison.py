from typing import Literal

import py_science.formula.comparison as comparison_service
import pytest
from py_science.formula import (
    AnalysisFailure,
    CandidateComparisonRequest,
    CandidateComparisonSuccess,
    CandidateComputation,
    CandidateOutputComparison,
    CandidateOutputMapping,
    CandidateTargetReference,
    CandidateWorkComparison,
    EquationRequest,
    EquationTarget,
    ExpressionTarget,
    FormulaSyntax,
    IdentityEvidence,
    IndexDomain,
    MathematicalDomain,
    PropertyEvidence,
    QueryAnswer,
    VariableDeclaration,
    analyze,
    compare_candidates,
)
from py_science.formula.expressions import ExpressionTooComplex
from pydantic import ValidationError


def _reference(candidate: str, equation: str | None = None) -> CandidateTargetReference:
    target = ExpressionTarget() if equation is None else EquationTarget(name=equation)
    return CandidateTargetReference(candidate=candidate, target=target)


def _mapping(
    name: str,
    first: str | None = None,
    second: str | None = None,
    *,
    reverse: bool = False,
) -> CandidateOutputMapping:
    targets = (
        _reference("first", first),
        _reference("second", second),
    )
    return CandidateOutputMapping(
        name=name,
        targets=tuple(reversed(targets)) if reverse else targets,
    )


def _expression_request(
    first: str = "x",
    second: str = "x",
) -> CandidateComparisonRequest:
    return CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        candidates=(
            CandidateComputation(name="first", expression=first),
            CandidateComputation(name="second", expression=second),
        ),
        outputs=(_mapping("value"),),
    )


def test_expression_candidates_disprove_before_work_preference() -> None:
    result = compare_candidates(_expression_request("x + 1", "x + 2"))

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.semantic_status == "disproved"
    assert result.work_comparison.status == "not_comparable"
    assert result.work_comparison.delta == "0"
    assert result.work_comparison.evidence is None


def test_identical_rational_outputs_retain_denominator_qualification() -> None:
    result = compare_candidates(_expression_request("1 / d", "1 / d"))

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.outputs[0].answer.conclusion == "proved_under_assumptions"
    assert result.outputs[0].answer.conditions == ("d != 0",)
    assert result.semantic_status == "proved_equal_under_assumptions"


def test_scalar_producer_expansion_aligns_indexed_outputs_and_retains_work() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        variables={
            "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            "d": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(name="rate", expression="Eq(r, 1 / d)"),
                    EquationRequest(
                        name="out",
                        expression="Eq(y[i], x * r)",
                        domains={"i": IndexDomain(lower="0", upper="N")},
                    ),
                ),
            ),
            CandidateComputation(
                name="second",
                equations=(
                    EquationRequest(
                        name="out",
                        expression="Eq(z[j], x / d)",
                        domains={"j": IndexDomain(lower="0", upper="N")},
                    ),
                ),
            ),
        ),
        outputs=(_mapping("value", "out", "out"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    output = result.outputs[0]
    assert output.interface_status == "compatible"
    assert output.answer.conclusion == "proved_under_assumptions"
    assert output.answer.conditions == ("d != 0",)
    assert output.expanded_interpretations is not None
    assert tuple(item.normalized_sympy for item in output.expanded_interpretations) == (
        "x/d",
        "x/d",
    )
    assert result.candidates[0].analysis == analyze(
        request.analysis_request(request.candidates[0])
    )
    assert result.candidates[1].analysis == analyze(
        request.analysis_request(request.candidates[1])
    )
    assert result.candidates[0].aggregate_work != result.candidates[1].aggregate_work
    assert result.work_comparison.delta == "-1"
    assert result.work_comparison.status == "second_lower"


def test_mapping_entries_are_correlated_by_candidate_not_tuple_position() -> None:
    request = _expression_request()
    reversed_request = request.model_copy(
        update={"outputs": (_mapping("value", reverse=True),)}
    )

    result = compare_candidates(reversed_request)

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.semantic_status == "proved_equal"
    assert tuple(target.candidate for target in result.outputs[0].targets) == (
        "first",
        "second",
    )


def test_effective_domains_must_match_before_value_comparison() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(
                        name="out",
                        expression="Eq(y[i], i)",
                        domains={"i": IndexDomain(lower="0", upper="3")},
                    ),
                ),
            ),
            CandidateComputation(
                name="second",
                equations=(
                    EquationRequest(
                        name="out",
                        expression="Eq(z[j], j)",
                        domains={"j": IndexDomain(lower="0", upper="4")},
                    ),
                ),
            ),
        ),
        outputs=(_mapping("value", "out", "out"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.outputs[0].interface_status == "incompatible"
    assert result.outputs[0].answer.conclusion == "inapplicable"
    assert result.semantic_status == "unresolved"
    assert result.work_comparison.status == "not_comparable"


def test_sum_binders_are_alpha_renamed_during_producer_expansion() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        variables={
            "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(
                        name="producer",
                        expression="Eq(Q[i], Sum(x, (j, 0, N)))",
                        domains={"i": IndexDomain(lower="0", upper="N")},
                    ),
                    EquationRequest(
                        name="out",
                        expression="Eq(y[j], Q[j])",
                        domains={"j": IndexDomain(lower="0", upper="N")},
                    ),
                ),
            ),
            CandidateComputation(
                name="second",
                equations=(
                    EquationRequest(
                        name="out",
                        expression="Eq(z[k], Sum(x, (j, 0, N)))",
                        domains={"k": IndexDomain(lower="0", upper="N")},
                    ),
                ),
            ),
        ),
        outputs=(_mapping("value", "out", "out"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    output = result.outputs[0]
    assert output.answer.conclusion == "unresolved"
    assert "bounded rational family" in output.answer.blockers[0]
    assert output.expanded_interpretations is not None
    left, right = output.expanded_interpretations
    assert left.normalized_sympy == right.normalized_sympy
    assert "comparison_sum_0" in left.normalized_sympy


def test_domain_expansion_overflow_is_a_correlated_unresolved_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expander = comparison_service._Expander  # pyright: ignore[reportPrivateUsage]

    def overflow(*_args: object, **_kwargs: object) -> None:
        raise ExpressionTooComplex("comparison domain expansion exceeds its bound")

    monkeypatch.setattr(expander, "expand", overflow)
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(
                        name="out",
                        expression="Eq(y[i], i)",
                        domains={"i": IndexDomain(lower="0", upper="2")},
                    ),
                ),
            ),
            CandidateComputation(
                name="second",
                equations=(
                    EquationRequest(
                        name="out",
                        expression="Eq(z[j], j)",
                        domains={"j": IndexDomain(lower="0", upper="2")},
                    ),
                ),
            ),
        ),
        outputs=(_mapping("value", "out", "out"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.outputs[0].interface_status == "unresolved"
    assert result.outputs[0].answer.conclusion == "unresolved"
    assert "domain expansion" in result.outputs[0].answer.blockers[0]


def test_expansion_node_budget_is_aggregate_across_recursive_producers() -> None:
    equations = [EquationRequest(name="p0", expression="Eq(p0, x)")]
    for position in range(1, 15):
        equations.append(
            EquationRequest(
                name=f"p{position}",
                expression=f"Eq(p{position}, p{position - 1} + p{position - 1})",
            )
        )
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        candidates=(
            CandidateComputation(name="first", equations=tuple(equations)),
            CandidateComputation(name="second", expression="x"),
        ),
        outputs=(_mapping("value", "p14", None),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.outputs[0].interface_status == "compatible"
    assert result.outputs[0].expanded_interpretations is None
    assert result.outputs[0].answer.conclusion == "unresolved"
    assert "aggregate node bound" in result.outputs[0].answer.blockers[0]


def test_exact_sign_chart_reports_work_crossover() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        variables={
            "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(name="out", expression="Eq(y, x)"),
                    EquationRequest(
                        name="extra",
                        expression="Eq(a[i], x + 1)",
                        domains={"i": IndexDomain(lower="0", upper="N")},
                    ),
                ),
            ),
            CandidateComputation(
                name="second",
                equations=(
                    EquationRequest(name="out", expression="Eq(z, x)"),
                    EquationRequest(name="extra", expression="Eq(b, x + 1 + 1)"),
                ),
            ),
        ),
        outputs=(_mapping("value", "out", "out"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    work = result.work_comparison
    assert work.delta == "1 - N"
    assert work.status == "crossover"
    assert isinstance(work.evidence, PropertyEvidence)
    assert work.evidence.intervals == (
        "(-oo, 1): positive",
        "(1, oo): negative",
        "1: zero",
    )
    assert work.model_dump_json() == (
        '{"metric":"aggregate_abstract_work","candidate_names":["first","second"],'
        '"candidate_works":["N + 1","2"],"delta":"1 - N","status":"crossover",'
        '"conditions":[],"assumptions_used":[],"relevant_unsupported_assumptions":[],'
        '"blockers":[],"evidence":{"kind":"property","value":"sign chart",'
        '"intervals":["(-oo, 1): positive","(1, oo): negative","1: zero"]}}'
    )


def test_unknown_and_nonfinite_work_never_produce_a_preference() -> None:
    def request(extra: str) -> CandidateComparisonRequest:
        return CandidateComparisonRequest(
            syntax=FormulaSyntax.SYMPY,
            variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            candidates=(
                CandidateComputation(name="first", equations=(
                    EquationRequest(name="out", expression="Eq(y, x)"),
                    EquationRequest(name="extra", expression=f"Eq(u, {extra})"),
                )),
                CandidateComputation(name="second", equations=(
                    EquationRequest(name="out", expression="Eq(z, x)"),
                    EquationRequest(name="extra", expression=f"Eq(v, {extra})"),
                )),
            ),
            outputs=(_mapping("value", "out", "out"),),
        )

    unknown = compare_candidates(request("opaque(x)"))
    nonfinite = compare_candidates(request("oo"))

    assert isinstance(unknown, CandidateComparisonSuccess)
    assert unknown.semantic_status == "proved_equal"
    assert unknown.work_comparison.status == "unresolved"
    assert unknown.work_comparison.delta == "0"
    assert unknown.work_comparison.blockers == ("unknown primitive costs: C_opaque",)
    assert isinstance(nonfinite, CandidateComparisonSuccess)
    assert nonfinite.semantic_status == "proved_equal"
    assert nonfinite.work_comparison.status == "unresolved"
    assert nonfinite.work_comparison.delta is None
    assert nonfinite.candidates[0].aggregate_work is None


def test_constant_positive_delta_reports_first_candidate_lower() -> None:
    result = compare_candidates(_expression_request("x", "x + 0"))

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.semantic_status == "proved_equal"
    assert result.work_comparison.delta == "1"
    assert result.work_comparison.status == "first_lower"
    assert isinstance(result.work_comparison.evidence, PropertyEvidence)
    assert result.work_comparison.model_dump_json() == (
        '{"metric":"aggregate_abstract_work","candidate_names":["first","second"],'
        '"candidate_works":["0","1"],"delta":"1","status":"first_lower",'
        '"conditions":[],"assumptions_used":[],"relevant_unsupported_assumptions":[],'
        '"blockers":[],"evidence":{"kind":"property",'
        '"value":"exact constant aggregate-work sign",'
        '"intervals":["all values: positive"]}}'
    )


def test_multivariate_work_ordering_retains_delta_and_abstains() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        variables={
            "M": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "N": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(name="out", expression="Eq(y, x)"),
                    EquationRequest(
                        name="extra",
                        expression="Eq(a[i], x + 1)",
                        domains={"i": IndexDomain(lower="0", upper="M")},
                    ),
                ),
            ),
            CandidateComputation(
                name="second",
                equations=(
                    EquationRequest(name="out", expression="Eq(z, x)"),
                    EquationRequest(
                        name="extra",
                        expression="Eq(b[j], x + 1)",
                        domains={"j": IndexDomain(lower="0", upper="N")},
                    ),
                ),
            ),
        ),
        outputs=(_mapping("value", "out", "out"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, CandidateComparisonSuccess)
    assert result.semantic_status == "proved_equal"
    assert result.work_comparison.delta == "-M + N"
    assert result.work_comparison.status == "unresolved"
    assert result.work_comparison.evidence is None
    assert result.work_comparison.blockers


def test_invalid_mapped_interfaces_are_correlated_inapplicable_results() -> None:
    real_x = {"x": VariableDeclaration(domain=MathematicalDomain.REAL)}
    cases = (
        CandidateComparisonRequest(
            syntax=FormulaSyntax.SYMPY,
            variables=real_x,
            candidates=(
                CandidateComputation(
                    name="first",
                    equations=(EquationRequest(name="out", expression="Eq(y, x)"),),
                ),
                CandidateComputation(name="second", expression="x"),
            ),
            outputs=(_mapping("value"),),
        ),
        CandidateComparisonRequest(
            syntax=FormulaSyntax.SYMPY,
            variables=real_x,
            candidates=(
                CandidateComputation(name="first", expression="x"),
                CandidateComputation(
                    name="second",
                    equations=(EquationRequest(name="out", expression="Eq(z, x)"),),
                ),
            ),
            outputs=(_mapping("value", "missing", "out"),),
        ),
        CandidateComparisonRequest(
            syntax=FormulaSyntax.SYMPY,
            variables=real_x,
            candidates=(
                CandidateComputation(
                    name="first",
                    equations=(EquationRequest(name="out", expression="Eq(y, x)"),),
                ),
                CandidateComputation(
                    name="second",
                    equations=(
                        EquationRequest(
                            name="out",
                            expression="Eq(z[i], x)",
                            domains={"i": IndexDomain(lower="0", upper="2")},
                        ),
                    ),
                ),
            ),
            outputs=(_mapping("value", "out", "out"),),
        ),
        CandidateComparisonRequest(
            syntax=FormulaSyntax.SYMPY,
            variables=real_x,
            candidates=(
                CandidateComputation(
                    name="first",
                    equations=(
                        EquationRequest(
                            name="out",
                            expression="Eq(y[i], x)",
                            domains={"i": IndexDomain(lower="0", upper="2")},
                        ),
                    ),
                ),
                CandidateComputation(
                    name="second",
                    equations=(
                        EquationRequest(
                            name="out",
                            expression="Eq(z[j, k], x)",
                            domains={
                                "j": IndexDomain(lower="0", upper="2"),
                                "k": IndexDomain(lower="0", upper="2"),
                            },
                        ),
                    ),
                ),
            ),
            outputs=(_mapping("value", "out", "out"),),
        ),
    )

    for request in cases:
        result = compare_candidates(request)
        assert isinstance(result, CandidateComparisonSuccess)
        assert result.outputs[0].interface_status == "incompatible"
        assert result.outputs[0].answer.conclusion == "inapplicable"
        assert result.outputs[0].answer.blockers


def test_candidate_cycle_failure_is_prefixed_to_candidate() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        candidates=(
            CandidateComputation(
                name="first",
                equations=(
                    EquationRequest(name="a", expression="Eq(a, b)"),
                    EquationRequest(name="b", expression="Eq(b, a)"),
                ),
            ),
            CandidateComputation(name="second", expression="x"),
        ),
        outputs=(_mapping("value", "a", None),),
    )

    result = compare_candidates(request)

    assert isinstance(result, AnalysisFailure)
    assert result.error.source is not None
    assert result.error.source.path.startswith("candidates[0]")


def test_semantic_disproof_precedence_is_output_order_independent() -> None:
    candidates = (
        CandidateComputation(
            name="first",
            equations=(
                EquationRequest(name="same", expression="Eq(a, x)"),
                EquationRequest(name="different", expression="Eq(b, x + 1)"),
            ),
        ),
        CandidateComputation(
            name="second",
            equations=(
                EquationRequest(name="same", expression="Eq(c, x)"),
                EquationRequest(name="different", expression="Eq(d, x + 2)"),
            ),
        ),
    )
    mappings = (
        _mapping("same", "same", "same"),
        _mapping("different", "different", "different"),
    )
    statuses: list[str] = []
    for outputs in (mappings, tuple(reversed(mappings))):
        result = compare_candidates(
            CandidateComparisonRequest(
                syntax=FormulaSyntax.SYMPY,
                variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
                candidates=candidates,
                outputs=outputs,
            )
        )
        assert isinstance(result, CandidateComparisonSuccess)
        statuses.append(result.semantic_status)
    assert statuses == ["disproved", "disproved"]


def test_candidate_failures_are_localized_under_candidate_index() -> None:
    request = CandidateComparisonRequest(
        syntax=FormulaSyntax.SYMPY,
        candidates=(
            CandidateComputation(name="first", expression="("),
            CandidateComputation(name="second", expression="x"),
        ),
        outputs=(_mapping("value"),),
    )

    result = compare_candidates(request)

    assert isinstance(result, AnalysisFailure)
    assert result.error.source is not None
    assert result.error.source.path == "candidates[0].expression"


def test_request_rejects_duplicate_foreign_and_surplus_mapping_shapes() -> None:
    base = _expression_request().model_dump()
    duplicate = {
        **base,
        "candidates": (
            {"name": "same", "expression": "x", "equations": ()},
            {"name": "same", "expression": "x", "equations": ()},
        ),
    }
    foreign = {
        **base,
        "outputs": (
            {
                "name": "value",
                "targets": (
                    {"candidate": "first", "target": {"kind": "expression"}},
                    {"candidate": "foreign", "target": {"kind": "expression"}},
                ),
            },
        ),
    }
    surplus = {**base, "scenarios": ()}

    for payload in (duplicate, foreign, surplus):
        with pytest.raises(ValidationError):
            CandidateComparisonRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("constant", "message"),
    (
        ("MAX_REQUEST_BYTES", "byte bound"),
        ("MAX_REQUEST_NODES", "mathematical structure"),
    ),
)
def test_comparison_request_aggregate_bounds_can_fail(
    monkeypatch: pytest.MonkeyPatch, constant: str, message: str
) -> None:
    monkeypatch.setattr(comparison_service, constant, 1)

    result = compare_candidates(_expression_request())

    assert isinstance(result, AnalysisFailure)
    assert message in result.error.message


def test_comparison_result_bound_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "MAX_RESULT_BYTES", 1)

    result = compare_candidates(_expression_request())

    assert isinstance(result, AnalysisFailure)
    assert "result exceeds its size bound" in result.error.message


def test_unexpected_comparison_reasoning_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unexpected reasoning defect")

    monkeypatch.setattr(comparison_service.ReasoningContext, "build", unexpected)

    with pytest.raises(RuntimeError, match="unexpected reasoning defect"):
        compare_candidates(_expression_request("x", "x + 0"))


def test_unexpected_comparison_backend_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unexpected comparison defect")

    monkeypatch.setattr(comparison_service, "equivalence_answer", unexpected)

    with pytest.raises(RuntimeError, match="unexpected comparison defect"):
        compare_candidates(_expression_request("x", "x + 0"))


def test_result_models_reject_invalid_qualification_truth_tables() -> None:
    targets = (_reference("first"), _reference("second"))
    with pytest.raises(ValidationError):
        CandidateOutputComparison(
            name="value",
            targets=targets,
            interface_status="incompatible",
            answer=QueryAnswer(conclusion="inapplicable"),
        )
    with pytest.raises(ValidationError):
        CandidateOutputComparison(
            name="value",
            targets=targets,
            interface_status="compatible",
            expanded_interpretations=None,
            answer=QueryAnswer(
                conclusion="proved",
                evidence=IdentityEvidence(statement="invalid without interpretations"),
            ),
        )
    with pytest.raises(ValidationError):
        CandidateWorkComparison(
            candidate_names=("first", "second"),
            candidate_works=("1", "1"),
            status="equal",
            delta=None,
            evidence=IdentityEvidence(statement="missing delta"),
        )
    with pytest.raises(ValidationError):
        CandidateWorkComparison(
            candidate_names=("first", "second"),
            candidate_works=("1", "2"),
            delta="1",
            status="first_lower",
            evidence=None,
        )
    comparable_cases: tuple[
        tuple[
            Literal["equal", "first_lower", "second_lower", "crossover"],
            IdentityEvidence | PropertyEvidence,
        ],
        ...,
    ] = (
        ("equal", IdentityEvidence(statement="equal")),
        ("first_lower", PropertyEvidence(value="positive")),
        ("second_lower", PropertyEvidence(value="negative")),
        ("crossover", PropertyEvidence(value="mixed")),
    )
    for status, evidence in comparable_cases:
        with pytest.raises(ValidationError):
            CandidateWorkComparison(
                candidate_names=("first", "second"),
                candidate_works=("1", "2"),
                delta="1",
                status=status,
                blockers=("invalid comparable blocker",),
                evidence=evidence,
            )
