from typing import Never

import pytest

import pi_science.service as service
import pi_science.sympy_backend as sympy_backend
from pi_science import (
    EvaluationErrorCode,
    EvaluationFailure,
    EvaluationRequest,
    FormulaSyntax,
)
from pi_science.expressions import Expression, Symbol


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
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x")

    outcome = service.evaluate(request)

    assert isinstance(outcome, EvaluationFailure)
    assert outcome.error.code is EvaluationErrorCode.NORMALIZATION_FAILED


def test_service_does_not_hide_unexpected_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(_expression: Expression) -> Never:
        raise RuntimeError("programming defect")

    monkeypatch.setattr(service, "render", fail_unexpectedly)
    request = EvaluationRequest(syntax=FormulaSyntax.SYMPY, expression="x")

    with pytest.raises(RuntimeError, match="programming defect"):
        service.evaluate(request)
