# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Private optimizer owner."""

from __future__ import annotations

from dataclasses import dataclass

MAX_OPTIMIZATION_INSPECTIONS = 16_384
MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS = 131_072
MAX_OPTIMIZATION_WHOLE_INSPECTIONS = 147_456
MAX_OPTIMIZATION_CANDIDATES = 256
MAX_OPTIMIZATION_COMPLETE_REANALYSES = 8
MAX_OPTIMIZATION_EXPANDED_PARENTS = 8
MAX_OPTIMIZATION_RETAINED_STATES = 8
MAX_OPTIMIZATION_TRANSFORM_NODES = 8_192
MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES = 32_768
MAX_OPTIMIZATION_PROOFS = 256
MAX_OPTIMIZATION_PROOF_NODES = 32_768
MAX_OPTIMIZATION_WORK_NODES = 32_768
MAX_OPTIMIZATION_WHOLE_PROOFS = 512
MAX_OPTIMIZATION_WHOLE_PROOF_NODES = 65_536
MAX_OPTIMIZATION_WHOLE_WORK_NODES = 65_536
MAX_OPTIMIZATION_FINAL_STATES = 16
MAX_OPTIMIZATION_FINAL_PROOFS = 16
MAX_OPTIMIZATION_FINAL_PROOF_NODES = 32_768
MAX_OPTIMIZATION_FINAL_WORK_NODES = 32_768
MAX_HORNER_TARGET_NODES = 512
MAX_HORNER_VARIABLES = 1
MAX_HORNER_DEGREE = 8
MAX_HORNER_TERMS = 64
MAX_HORNER_GENERATED_NODES = 512


@dataclass(frozen=True, slots=True)
class _OptimizationBudgetConfig:
    """Private test seam for every fixed composed-search allowance."""

    inspections: int = MAX_OPTIMIZATION_INSPECTIONS
    depth_two_inspections: int = MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS
    whole_inspections: int = MAX_OPTIMIZATION_WHOLE_INSPECTIONS
    candidates: int = MAX_OPTIMIZATION_CANDIDATES
    complete_reanalyses: int = MAX_OPTIMIZATION_COMPLETE_REANALYSES
    expanded_parents: int = MAX_OPTIMIZATION_EXPANDED_PARENTS
    retained_states: int = MAX_OPTIMIZATION_RETAINED_STATES
    aggregate_transform_nodes: int = MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES
    proofs: int = MAX_OPTIMIZATION_PROOFS
    proof_nodes: int = MAX_OPTIMIZATION_PROOF_NODES
    work_nodes: int = MAX_OPTIMIZATION_WORK_NODES
    whole_proofs: int = MAX_OPTIMIZATION_WHOLE_PROOFS
    whole_proof_nodes: int = MAX_OPTIMIZATION_WHOLE_PROOF_NODES
    whole_work_nodes: int = MAX_OPTIMIZATION_WHOLE_WORK_NODES
    final_states: int = MAX_OPTIMIZATION_FINAL_STATES
    final_proofs: int = MAX_OPTIMIZATION_FINAL_PROOFS
    final_proof_nodes: int = MAX_OPTIMIZATION_FINAL_PROOF_NODES
    final_work_nodes: int = MAX_OPTIMIZATION_FINAL_WORK_NODES


def _default_budget_config() -> _OptimizationBudgetConfig:
    """Read module limits at request time so monkeypatched private seams remain useful."""
    return _OptimizationBudgetConfig(
        inspections=MAX_OPTIMIZATION_INSPECTIONS,
        depth_two_inspections=MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS,
        whole_inspections=MAX_OPTIMIZATION_WHOLE_INSPECTIONS,
        candidates=MAX_OPTIMIZATION_CANDIDATES,
        complete_reanalyses=MAX_OPTIMIZATION_COMPLETE_REANALYSES,
        expanded_parents=MAX_OPTIMIZATION_EXPANDED_PARENTS,
        retained_states=MAX_OPTIMIZATION_RETAINED_STATES,
        aggregate_transform_nodes=MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES,
        proofs=MAX_OPTIMIZATION_PROOFS,
        proof_nodes=MAX_OPTIMIZATION_PROOF_NODES,
        work_nodes=MAX_OPTIMIZATION_WORK_NODES,
        whole_proofs=MAX_OPTIMIZATION_WHOLE_PROOFS,
        whole_proof_nodes=MAX_OPTIMIZATION_WHOLE_PROOF_NODES,
        whole_work_nodes=MAX_OPTIMIZATION_WHOLE_WORK_NODES,
        final_states=MAX_OPTIMIZATION_FINAL_STATES,
        final_proofs=MAX_OPTIMIZATION_FINAL_PROOFS,
        final_proof_nodes=MAX_OPTIMIZATION_FINAL_PROOF_NODES,
        final_work_nodes=MAX_OPTIMIZATION_FINAL_WORK_NODES,
    )


@dataclass(slots=True)
class _WholeTransitionBudget:
    """Whole-request transition ceilings shared by both search depths."""

    config: _OptimizationBudgetConfig
    inspections: int = 0
    proofs: int = 0
    proof_nodes: int = 0
    work_nodes: int = 0

    @staticmethod
    def _accept(resource: str, measured: int, configured: int) -> None:
        if measured > configured:
            raise _BudgetExhausted(resource, measured, configured)

    def inspect(self, amount: int) -> None:
        self.inspections += amount
        self._accept(
            "whole-request inspected nodes", self.inspections, self.config.whole_inspections
        )

    def proof(self, nodes: int) -> None:
        self.proofs += 1
        self._accept("whole-request proof steps", self.proofs, self.config.whole_proofs)
        self.proof_nodes += nodes
        self._accept("whole-request proof nodes", self.proof_nodes, self.config.whole_proof_nodes)

    def work(self, nodes: int) -> None:
        self.work_nodes += nodes
        self._accept(
            "whole-request work-comparison nodes",
            self.work_nodes,
            self.config.whole_work_nodes,
        )


@dataclass(slots=True)
class _OptimizationBudget:
    config: _OptimizationBudgetConfig = _OptimizationBudgetConfig()
    label: str = "transition"
    whole: _WholeTransitionBudget | None = None
    inspections: int = 0
    candidates: int = 0
    complete_reanalyses: int = 0
    expanded_parents: int = 0
    retained_states: int = 0
    aggregate_transform_nodes: int = 0
    proofs: int = 0
    proof_nodes: int = 0
    work_nodes: int = 0

    def resource(self, resource: str) -> str:
        return f"{self.label} {resource}" if self.label else resource

    @staticmethod
    def _accept(resource: str, measured: int, configured: int) -> None:
        if measured > configured:
            raise _BudgetExhausted(resource, measured, configured)

    def inspect(self, amount: int = 1) -> None:
        measured = self.inspections + amount
        self._accept(self.resource("inspected nodes"), measured, self.config.inspections)
        if self.whole is not None:
            self.whole.inspect(amount)
        self.inspections = measured

    def candidate(self) -> None:
        measured = self.candidates + 1
        self._accept(self.resource("generated transitions"), measured, self.config.candidates)
        self.candidates = measured

    def reanalysis(self) -> None:
        measured = self.complete_reanalyses + 1
        self._accept(
            self.resource("complete candidate reanalyses"),
            measured,
            self.config.complete_reanalyses,
        )
        self.complete_reanalyses = measured

    def parent(self) -> None:
        measured = self.expanded_parents + 1
        self._accept(self.resource("expanded parents"), measured, self.config.expanded_parents)
        self.expanded_parents = measured

    def retain(self) -> None:
        measured = self.retained_states + 1
        self._accept(self.resource("retained states"), measured, self.config.retained_states)
        self.retained_states = measured

    def transformation(self, nodes: int) -> None:
        self._accept("per-candidate transformation nodes", nodes, MAX_OPTIMIZATION_TRANSFORM_NODES)
        measured = self.aggregate_transform_nodes + nodes
        self._accept(
            self.resource("aggregate transformation nodes"),
            measured,
            self.config.aggregate_transform_nodes,
        )
        self.aggregate_transform_nodes = measured

    def proof(self, nodes: int) -> None:
        measured = self.proofs + 1
        self._accept(self.resource("proof steps"), measured, self.config.proofs)
        measured_nodes = self.proof_nodes + nodes
        self._accept(self.resource("proof nodes"), measured_nodes, self.config.proof_nodes)
        if self.whole is not None:
            self.whole.proof(nodes)
        self.proofs = measured
        self.proof_nodes = measured_nodes

    def work(self, nodes: int) -> None:
        measured = self.work_nodes + nodes
        self._accept(self.resource("work-comparison nodes"), measured, self.config.work_nodes)
        if self.whole is not None:
            self.whole.work(nodes)
        self.work_nodes = measured


class _BudgetExhausted(RuntimeError):
    def __init__(self, resource: str, measured: int, configured: int) -> None:
        self.resource = resource
        self.measured = measured
        self.configured = configured
        super().__init__(
            f"optimization {resource} budget exhausted "
            f"(measured {measured}, configured {configured})"
        )
