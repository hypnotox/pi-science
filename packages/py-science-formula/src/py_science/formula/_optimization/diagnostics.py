# pyright: reportPrivateUsage=false, reportUnusedClass=false
"""Private bounded accounting for optimization work already performed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from py_science.formula.models import OptimizationKind

_OutcomeReason = Literal[
    "missing_primitive_cost",
    "unproved_domain_or_cardinality",
    "evaluator_limit",
]
_RequiredInformation = Literal[
    "declare_primitive_cost",
    "declare_domain_or_cardinality",
    "reduce_evaluator_complexity",
]


@dataclass(frozen=True, slots=True)
class _OutcomeBlocker:
    """A safe, candidate-free fact captured by existing optimizer work."""

    reason: _OutcomeReason
    required_information: _RequiredInformation
    family: OptimizationKind | None = None
    target: str | None = None


@dataclass(slots=True)
class _OutcomeAccounting:
    """Bound observed search outcomes without changing search decisions."""

    generation_events: int = 0
    proposals: int = 0
    transition_verifications: int = 0
    rejected_before_final_acceptance: int = 0
    final_acceptance_attempts: int = 0
    _blockers: dict[tuple[object, ...], _OutcomeBlocker] = field(default_factory=lambda: {})

    def generation_observed(self, proposals: int = 0) -> None:
        self.generation_events += 1
        self.proposals += proposals

    def transition_verified(self) -> None:
        self.transition_verifications += 1

    def transition_rejected(self) -> None:
        self.rejected_before_final_acceptance += 1

    def final_acceptance_observed(self) -> None:
        self.final_acceptance_attempts += 1

    @property
    def blockers(self) -> tuple[_OutcomeBlocker, ...]:
        return tuple(self._blockers[key] for key in sorted(self._blockers))

    def missing_primitive_cost(self, family: OptimizationKind, target: str) -> None:
        self._record(
            _OutcomeBlocker("missing_primitive_cost", "declare_primitive_cost", family, target)
        )

    def unproved_domain_or_cardinality(self, family: OptimizationKind, target: str) -> None:
        self._record(
            _OutcomeBlocker(
                "unproved_domain_or_cardinality",
                "declare_domain_or_cardinality",
                family,
                target,
            )
        )

    def evaluator_limit(self, family: OptimizationKind, target: str) -> None:
        self._record(
            _OutcomeBlocker("evaluator_limit", "reduce_evaluator_complexity", family, target)
        )

    def _record(self, blocker: _OutcomeBlocker) -> None:
        key = (blocker.reason, blocker.required_information, blocker.family, blocker.target)
        if len(self._blockers) < 16 or key in self._blockers:
            self._blockers.setdefault(key, blocker)
