"""Internal, bounded diagnostics for formula-query applicability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RationalFailureKind = Literal[
    "nodes",
    "unsupported_form",
    "degree",
    "exponent",
    "coefficient_bits",
    "expanded_terms",
]

AsymptoticFailureKind = Literal[
    "nodes",
    "resource",
    "term_count",
    "reconstruction",
    "rendering",
    "rational_measure",
    "rational_normalization",
    "real_parameters",
    "parameter_denominator",
    "specific",
]

DiagnosticReason = Literal[
    "exceeds bounded rational node limit",
    "is outside the bounded rational family",
    "exceeds bounded rational degree limit",
    "exceeds bounded rational exponent limit",
    "exceeds bounded rational coefficient-bit limit",
    "exceeds bounded rational expanded-term limit",
    "cannot be prepared by bounded query reasoning",
    "cannot be translated by the bounded rational backend",
    "cannot be cancelled by the bounded rational backend",
    "cannot be split into a bounded rational fraction",
    "is ambiguous",
    "exceeds its bounded node limit",
    "has no sibling sums",
    "has too many sibling sums",
    "has a negative-infinity upper bound",
    "contains forbidden structure",
    "contains unsupported enclosing structure",
    "exceeds its bounded resource limits",
    "exceeds its bound",
    "depend on the summation index",
    "does not match (a*k+b)*r**k",
    "exceeds its bounded exponent limit",
    "is neither a bounded rational expression nor a supported linear-exponential expression",
    "parameters are not proved real",
    "denominator depends on non-query parameters",
    "term count exceeds its bound",
    "reconstruction exceeds its bound",
    "rendering exceeds its bound",
]

RATIONAL_FAILURE_REASONS: dict[RationalFailureKind, DiagnosticReason] = {
    "nodes": "exceeds bounded rational node limit",
    "unsupported_form": "is outside the bounded rational family",
    "degree": "exceeds bounded rational degree limit",
    "exponent": "exceeds bounded rational exponent limit",
    "coefficient_bits": "exceeds bounded rational coefficient-bit limit",
    "expanded_terms": "exceeds bounded rational expanded-term limit",
}


@dataclass(frozen=True, slots=True)
class QueryDiagnostic:
    """One safe refusal reason rendered through the existing blocker contract."""

    subject: str
    reason: DiagnosticReason
    observed: int | None = None
    configured: int | None = None
    recovery: str | None = None

    def render(self) -> str:
        text = f"{self.subject} {self.reason}"
        if self.observed is not None and self.configured is not None:
            text += f": observed {self.observed}, configured {self.configured}"
        if self.recovery is not None:
            text += f"; {self.recovery}"
        return text
