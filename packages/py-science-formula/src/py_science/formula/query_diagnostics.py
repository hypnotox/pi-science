"""Internal, bounded diagnostics for formula-query applicability."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryDiagnostic:
    """One safe refusal reason rendered through the existing blocker contract."""

    subject: str
    reason: str
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
