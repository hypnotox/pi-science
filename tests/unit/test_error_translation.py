from types import SimpleNamespace
from typing import Never

import py_science.formula.parser as formula_parser
import py_science.formula.service as service
import py_science.formula.sympy_backend as sympy_backend
import pytest
from py_science.formula import (
    AnalysisErrorCode,
    AnalysisFailure,
    AnalysisRequest,
    Assumption,
    DirectedDefinition,
    FormulaSyntax,
    Scenario,
)
from py_science.formula.expressions import Expression, Symbol
from py_science.formula.parser import ParseFailure


def test_sympy_adapter_preserves_backend_failure_as_its_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_conversion(_expression: Expression) -> Never:
        raise ValueError("backend rejected expression")

    monkeypatch.setattr(sympy_backend, "_to_sympy", fail_conversion)

    with pytest.raises(sympy_backend.NormalizationError) as raised:
        sympy_backend.render(Symbol("x"))

    assert isinstance(raised.value.__cause__, ValueError)


def test_service_translates_only_named_normalization_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_render(_expression: Expression) -> Never:
        raise sympy_backend.NormalizationError("normalization failed")

    monkeypatch.setattr(service, "render", fail_render)
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x")

    outcome = service.analyze(request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.code is AnalysisErrorCode.NORMALIZATION_FAILED


def test_service_does_not_hide_unexpected_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(_expression: Expression) -> Never:
        raise RuntimeError("programming defect")

    monkeypatch.setattr(service, "render", fail_unexpectedly)
    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x")

    with pytest.raises(RuntimeError, match="programming defect"):
        service.analyze(request)


def test_parse_errors_include_exact_optional_diagnostic_shape() -> None:
    outcome = service.analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x +"))
    assert isinstance(outcome, AnalysisFailure)
    dumped = outcome.error.model_dump(mode="json")
    assert set(dumped) == {"code", "message", "location", "source", "supported_alternative"}
    assert dumped["source"]["path"] == "expression"
    assert dumped["source"]["excerpt"] == "x +"
    assert dumped["location"] is None
    assert dumped["source"]["span"] is None


def test_offsetless_syntax_error_does_not_invent_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_parse(*_args: object, **_kwargs: object) -> Never:
        raise SyntaxError("missing precision")

    monkeypatch.setattr(formula_parser, "ast", SimpleNamespace(parse=fail_parse))
    parsed = formula_parser.parse_expression("x")
    assert isinstance(parsed, ParseFailure)
    assert parsed.line is None
    assert parsed.column is None
    assert parsed.end_line is None
    assert parsed.end_column is None


def test_known_token_span_is_end_exclusive() -> None:
    outcome = service.analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="1e3"))
    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.source is not None
    assert outcome.error.source.span is not None
    assert outcome.error.source.span.start.column == 0
    assert outcome.error.source.span.end.column == 3


def test_syntax_error_span_uses_utf8_byte_columns_after_unicode() -> None:
    outcome = service.analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="α + * 1")  # noqa: RUF001
    )
    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.source is not None
    assert outcome.error.source.span is not None
    assert outcome.error.source.span.start.column == 5
    assert outcome.error.source.span.end.column == 6


def test_parse_errors_identify_the_nested_request_source() -> None:
    outcome = service.analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            assumptions=(Assumption(name="broken", relationship="x +"),),
        )
    )
    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.source is not None
    assert outcome.error.source.path == "assumptions[0].relationship"
    assert outcome.error.source.excerpt == "x +"


@pytest.mark.parametrize(
    ("analysis_request", "path"),
    [
        (
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="x",
                assumptions=(Assumption(name="not_a_relationship", relationship="x + 1"),),
            ),
            "assumptions[0].relationship",
        ),
        (
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="x",
                definitions=(DirectedDefinition(variable="y", expression="Eq(y, x)"),),
            ),
            "definitions[0].expression",
        ),
        (
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression="x",
                scenarios=(Scenario(name="unknown", fixed={"y": 1}),),
            ),
            "scenarios[0].fixed.y",
        ),
    ],
)
def test_semantic_request_errors_identify_the_precise_field_without_coordinates(
    analysis_request: AnalysisRequest, path: str
) -> None:
    outcome = service.analyze(analysis_request)

    assert isinstance(outcome, AnalysisFailure)
    assert outcome.error.source is not None
    assert outcome.error.source.path == path
    assert outcome.error.source.span is None
    assert outcome.error.location is None
