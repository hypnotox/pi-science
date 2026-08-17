from typing import Never

import py_science.formula.service as service
import py_science.formula.sympy_backend as sympy_backend
import pytest
from py_science.formula import (
    AnalysisErrorCode,
    AnalysisFailure,
    AnalysisRequest,
    FormulaSyntax,
)
from py_science.formula.expressions import Expression, Symbol


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
    assert dumped["location"] == dumped["source"]["span"]["start"]
