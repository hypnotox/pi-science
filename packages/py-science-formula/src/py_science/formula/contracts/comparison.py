# ruff: noqa: E501
# pyright: reportPrivateUsage=false
import re
from typing import Annotated, Literal

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.contracts.common import (
    _NAME_PATTERN,
    MAX_ASSUMPTIONS,
    MAX_DEFINITIONS,
    MAX_EQUATIONS,
    MAX_FUNCTIONS,
    MAX_NAME_LENGTH,
    MAX_PRIMITIVE_COSTS,
    Assumption,
    DirectedDefinition,
    EquationRequest,
    EquationTarget,
    ExpressionTarget,
    FormulaSyntax,
    FunctionDefinition,
    Interpretation,
    PrimitiveCost,
    RelationshipUse,
    VariableDeclaration,
    _require_unique,
)
from py_science.formula.contracts.evidence import (
    BoundedQueryText,
    CounterexampleEvidence,
    IdentityEvidence,
    PropertyEvidence,
)
from py_science.formula.contracts.queries import QueryAnswer
from py_science.formula.contracts.reports import AnalysisFailure, AnalysisSuccess
from py_science.formula.contracts.requests import AnalysisRequest
from pydantic import Field, model_validator


class CandidateComputation(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)

    @model_validator(mode="after")
    def one_computation(self) -> "CandidateComputation":
        if self.name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        _require_unique((item.name for item in self.equations), "equation names")
        return self

    def to_analysis_request(self) -> "AnalysisRequest":
        # Shared fields are supplied by CandidateComparisonRequest at call time.
        raise RuntimeError("comparison computation must be bound to shared request metadata")


class CandidateTargetReference(StructuredModel):
    candidate: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: Annotated[ExpressionTarget | EquationTarget, Field(discriminator="kind")]


class CandidateOutputMapping(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    targets: tuple[CandidateTargetReference, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def ordinary_name(self) -> "CandidateOutputMapping":
        if self.name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return self


class CandidateComparisonRequest(StructuredModel):
    operation: Literal["compare_candidates"] = "compare_candidates"
    syntax: FormulaSyntax
    candidates: tuple[CandidateComputation, ...] = Field(min_length=2, max_length=2)
    outputs: tuple[CandidateOutputMapping, ...] = Field(min_length=1, max_length=32)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)

    @model_validator(mode="after")
    def comparison_shape(self) -> "CandidateComparisonRequest":
        _require_unique((item.name for item in self.candidates), "candidate names")
        _require_unique((item.name for item in self.outputs), "output names")
        names = {item.name for item in self.candidates}
        for position, output in enumerate(self.outputs):
            mapped = tuple(item.candidate for item in output.targets)
            if set(mapped) != names or len(set(mapped)) != 2:
                raise ValueError(
                    f"outputs[{position}].targets must map each candidate exactly once"
                )
        # Reuse the ordinary request validator for shared-name restrictions,
        # callable collisions, variable bounds, and each computation shape.
        for candidate in self.candidates:
            self.analysis_request(candidate)
        return self

    def analysis_request(self, candidate: CandidateComputation) -> "AnalysisRequest":
        return AnalysisRequest(
            syntax=self.syntax,
            expression=candidate.expression,
            equations=candidate.equations,
            variables=self.variables,
            functions=self.functions,
            primitive_costs=self.primitive_costs,
            assumptions=self.assumptions,
            definitions=self.definitions,
        )


class CandidateAnalysisReport(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    analysis: "AnalysisSuccess"
    aggregate_work: BoundedQueryText | None = None

    @model_validator(mode="after")
    def direct_work_variant(self) -> "CandidateAnalysisReport":
        finite = self.analysis.direct_work_applicability == "finite"
        if finite != (self.aggregate_work is not None):
            raise ValueError(
                "finite candidate analysis requires aggregate work and non-finite analysis forbids it"
            )
        if not finite and not self.analysis.direct_work_blockers:
            raise ValueError("non-finite candidate analysis requires blockers")
        return self


class CandidateOutputComparison(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    targets: tuple[CandidateTargetReference, CandidateTargetReference]
    interface_status: Literal["compatible", "incompatible", "unresolved"]
    expanded_interpretations: "tuple[Interpretation, Interpretation] | None" = None
    answer: "QueryAnswer"

    @model_validator(mode="after")
    def qualified_output_shape(self) -> "CandidateOutputComparison":
        answer = self.answer
        if answer.check is not None or answer.derived_candidates or answer.constraint_uses:
            raise ValueError(
                "comparison outputs require one unchecked answer without candidates or constraint uses"
            )
        if self.interface_status == "incompatible":
            if (
                self.expanded_interpretations is not None
                or answer.conclusion != "inapplicable"
                or not answer.blockers
                or answer.evidence is not None
            ):
                raise ValueError("incompatible output has an invalid qualified shape")
            return self
        if self.interface_status == "unresolved":
            if (
                self.expanded_interpretations is not None
                or answer.conclusion != "unresolved"
                or not answer.blockers
                or answer.evidence is not None
            ):
                raise ValueError("unresolved interface has an invalid qualified shape")
            return self
        if self.expanded_interpretations is None:
            if (
                answer.conclusion != "unresolved"
                or not answer.blockers
                or answer.evidence is not None
            ):
                raise ValueError("unexpanded compatible output must be unresolved")
            return self
        if answer.conclusion in {"proved", "proved_under_assumptions"}:
            if not isinstance(answer.evidence, IdentityEvidence):
                raise ValueError("proved comparison output requires identity evidence")
        elif answer.conclusion == "disproved":
            if not isinstance(answer.evidence, CounterexampleEvidence):
                raise ValueError("disproved comparison output requires counterexample evidence")
        elif answer.conclusion == "unresolved":
            if not answer.blockers or answer.evidence is not None:
                raise ValueError("unresolved comparison output requires blockers only")
        else:
            raise ValueError("compatible expanded output has an invalid conclusion")
        return self


class CandidateWorkComparison(StructuredModel):
    metric: Literal["aggregate_abstract_work"] = "aggregate_abstract_work"
    candidate_names: tuple[str, str]
    candidate_works: tuple[BoundedQueryText | None, BoundedQueryText | None]
    delta: BoundedQueryText | None = None
    status: Literal[
        "not_comparable",
        "equal",
        "first_lower",
        "second_lower",
        "crossover",
        "unresolved",
    ]
    conditions: tuple[BoundedQueryText, ...] = Field(default=(), max_length=256)
    assumptions_used: "tuple[RelationshipUse, ...]" = Field(default=(), max_length=128)
    relevant_unsupported_assumptions: tuple[BoundedQueryText, ...] = Field(
        default=(), max_length=128
    )
    blockers: tuple[BoundedQueryText, ...] = Field(default=(), max_length=128)
    evidence: IdentityEvidence | PropertyEvidence | None = None

    @model_validator(mode="after")
    def qualified_work_shape(self) -> "CandidateWorkComparison":
        if len(set(self.candidate_names)) != 2 or any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in self.candidate_names
        ):
            raise ValueError("work candidate names must be unique ordinary identifiers")
        finite = all(work is not None for work in self.candidate_works)
        if not finite and self.delta is not None:
            raise ValueError("unavailable candidate work forbids a delta")
        if self.status == "not_comparable":
            if not self.blockers or self.evidence is not None:
                raise ValueError("not-comparable work requires blockers and no evidence")
            return self
        if self.status == "unresolved":
            if not self.blockers or self.evidence is not None:
                raise ValueError("unresolved work requires blockers and no evidence")
            if finite and self.delta is None:
                raise ValueError("unresolved finite work requires its symbolic delta")
            return self
        if not finite or self.delta is None:
            raise ValueError("comparable work requires two finite works and a delta")
        if self.blockers:
            raise ValueError("comparable work cannot carry blockers")
        if self.status == "equal":
            if not isinstance(self.evidence, IdentityEvidence):
                raise ValueError("equal work requires identity evidence")
        elif not isinstance(self.evidence, PropertyEvidence):
            raise ValueError("winner and crossover work require property evidence")
        return self


class CandidateComparisonSuccess(StructuredModel):
    kind: Literal["candidate_comparison"] = "candidate_comparison"
    status: Literal["success"] = "success"
    candidates: tuple[CandidateAnalysisReport, CandidateAnalysisReport]
    outputs: tuple[CandidateOutputComparison, ...] = Field(min_length=1, max_length=32)
    semantic_status: Literal[
        "proved_equal", "proved_equal_under_assumptions", "disproved", "unresolved"
    ]
    work_comparison: CandidateWorkComparison

    @model_validator(mode="after")
    def correlated_result(self) -> "CandidateComparisonSuccess":
        names = tuple(candidate.name for candidate in self.candidates)
        if len(set(names)) != 2:
            raise ValueError("candidate report names must be unique")
        _require_unique((output.name for output in self.outputs), "output names")
        for output in self.outputs:
            if tuple(target.candidate for target in output.targets) != names:
                raise ValueError("output targets must follow candidate report order")
        conclusions = {output.answer.conclusion for output in self.outputs}
        expected_semantic = (
            "disproved"
            if "disproved" in conclusions
            else "unresolved"
            if conclusions & {"unresolved", "inapplicable"}
            else "proved_equal_under_assumptions"
            if "proved_under_assumptions" in conclusions
            else "proved_equal"
        )
        if self.semantic_status != expected_semantic:
            raise ValueError("semantic status does not match mapped outputs")
        expected_works = tuple(candidate.aggregate_work for candidate in self.candidates)
        if (
            self.work_comparison.candidate_names != names
            or self.work_comparison.candidate_works != expected_works
        ):
            raise ValueError("work comparison does not match candidate report order")
        semantic_established = self.semantic_status in {
            "proved_equal",
            "proved_equal_under_assumptions",
        }
        if semantic_established == (self.work_comparison.status == "not_comparable"):
            raise ValueError("work comparability does not match semantic status")
        return self


type CandidateComparisonOutcome = Annotated[
    CandidateComparisonSuccess | AnalysisFailure, Field(discriminator="status")
]
