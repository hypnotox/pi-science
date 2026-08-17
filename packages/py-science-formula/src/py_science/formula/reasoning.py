# ruff: noqa: E501
"""Conservative, deliberately small assumption-reasoning boundary for queries.

Unsupported relationships are retained by callers as qualifications rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class DomainFact:
    symbol: str
    lower: Fraction | None = None
    lower_strict: bool = False
    upper: Fraction | None = None
    upper_strict: bool = False

    def excludes_zero(self) -> bool:
        return (self.lower is not None and (self.lower > 0 or (self.lower == 0 and self.lower_strict))) or (self.upper is not None and (self.upper < 0 or (self.upper == 0 and self.upper_strict)))
