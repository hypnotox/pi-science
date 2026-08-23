# pyright: reportPrivateUsage=false, reportUnusedImport=false
# ruff: noqa: F401
"""Compatibility facade for bounded local optimization."""

from __future__ import annotations

from ._analysis.occurrences import _EvaluationScope, _Occurrence
from ._optimization.budgets import (
    MAX_HORNER_DEGREE,
    MAX_HORNER_GENERATED_NODES,
    MAX_HORNER_TARGET_NODES,
    MAX_HORNER_TERMS,
    MAX_HORNER_VARIABLES,
    MAX_OPTIMIZATION_AGGREGATE_TRANSFORM_NODES,
    MAX_OPTIMIZATION_CANDIDATES,
    MAX_OPTIMIZATION_COMPLETE_REANALYSES,
    MAX_OPTIMIZATION_DEPTH_TWO_INSPECTIONS,
    MAX_OPTIMIZATION_EXPANDED_PARENTS,
    MAX_OPTIMIZATION_FINAL_PROOF_NODES,
    MAX_OPTIMIZATION_FINAL_PROOFS,
    MAX_OPTIMIZATION_FINAL_STATES,
    MAX_OPTIMIZATION_FINAL_WORK_NODES,
    MAX_OPTIMIZATION_INSPECTIONS,
    MAX_OPTIMIZATION_PROOF_NODES,
    MAX_OPTIMIZATION_PROOFS,
    MAX_OPTIMIZATION_RETAINED_STATES,
    MAX_OPTIMIZATION_TRANSFORM_NODES,
    MAX_OPTIMIZATION_WHOLE_INSPECTIONS,
    MAX_OPTIMIZATION_WHOLE_PROOF_NODES,
    MAX_OPTIMIZATION_WHOLE_PROOFS,
    MAX_OPTIMIZATION_WHOLE_WORK_NODES,
    MAX_OPTIMIZATION_WORK_NODES,
    _BudgetExhausted,
    _default_budget_config,
    _OptimizationBudget,
    _OptimizationBudgetConfig,
    _WholeTransitionBudget,
)
from ._optimization.candidates import (
    _all_symbol_names,
    _CandidateComputation,
    _CandidateDescriptor,
    _canonical_output_expression,
    _canonical_output_index_names,
    _descriptor_from_recipe,
    _descriptor_sort_key,
    _generated_let_variants,
    _generated_name,
    _generated_reference,
    _generated_replacement_descriptor,
    _replace_paths,
    _replacement_descriptor,
    _scope_sort_key,
    _smallest_scope,
    _target_inputs,
    _wrap_complete_let,
)
from ._optimization.canonical import (
    _candidate_semantic_key,
    _canonical_state_key,
    _stable_json,
    _trace_key,
)
from ._optimization.families.cross_equation_sharing import _cross_equation_descriptors
from ._optimization.families.factoring import _factor_term, _factored
from ._optimization.families.horner import _horner_candidate
from ._optimization.families.redundant_operations import _neutral_replacement
from ._optimization.objectives import (
    _accepted_order,
    _adjacent_ordering_relation,
    _suggestion_order,
    compare_aggregate_work,
)
from ._optimization.replay import _complete_candidate, _RetainedAnalyzer
from ._optimization.search import (
    _FAMILY_ORDER,
    _complete_candidate_schedule,
    _generate_candidate_lanes,
    _generate_candidates,
    _optimization_report,
    _RetainedLaneCollector,
    _round_robin_descriptors,
    _SearchState,
    _state_preference,
    _unique_qualifications,
)
from ._optimization.verifier import (
    _abstract_opaque_atoms,
    _Accepted,
    _aggregate_scope,
    _as_work,
    _candidate_target_work,
    _exact_output_equivalence,
    _Exhausted,
    _intermediate_interpretation,
    _interpretation,
    _original_final_suggestion,
    _qualifications_compatible,
    _reasoning,
    _Rejected,
    _unique_uses,
    _verify_candidate,
)
from .expressions import substitute
from .reasoning import ReasoningContext
