# pyright: reportPrivateUsage=false
from typing import Annotated, Literal

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.contracts.common import (
    _NAME_PATTERN,
    MAX_NAME_LENGTH,
    ConstraintUse,
    DerivedTarget,
    EquationTarget,
    ExpressionTarget,
    Interpretation,
    RelationshipUse,
)
from py_science.formula.contracts.evidence import DerivedCandidate, QueryEvidence
from py_science.formula.exact_values import parse_exact_scalar
from pydantic import Field, field_validator, model_validator


class VariablePropertyCheck(StructuredModel):
    kind: Literal["valid_domain", "singularities", "monotonicity"]
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("variable")
    @classmethod
    def ordinary_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable


class SignPropertyCheck(StructuredModel):
    kind: Literal["sign"] = "sign"


type PropertyCheck = Annotated[
    VariablePropertyCheck | SignPropertyCheck, Field(discriminator="kind")
]


class QueryBase(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: EquationTarget | DerivedTarget | None = None

    @field_validator("name")
    @classmethod
    def ordinary_name(cls, name: str) -> str:
        if name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return name


class EquivalenceQuery(QueryBase):
    kind: Literal["equivalence"] = "equivalence"
    comparison: str = Field(min_length=1, max_length=262_144)


class ClosedFormQuery(QueryBase):
    kind: Literal["closed_form"] = "closed_form"


class PropertiesQuery(QueryBase):
    kind: Literal["properties"] = "properties"
    checks: tuple[PropertyCheck, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def unique_checks(self) -> "PropertiesQuery":
        if len({item.model_dump_json() for item in self.checks}) != len(self.checks):
            raise ValueError("property checks must be unique")
        return self


class LimitQuery(QueryBase):
    kind: Literal["limit"] = "limit"
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("variable")
    @classmethod
    def ordinary_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable

    point: str | int
    direction: Literal["left", "right", "both"] | None = None

    @model_validator(mode="after")
    def valid_point(self) -> "LimitQuery":
        if isinstance(self.point, int) and abs(self.point) > 9_007_199_254_740_991:
            raise ValueError("numeric point must be a JavaScript-safe integer")
        if str(self.point) not in {"oo", "-oo"} and parse_exact_scalar(str(self.point)) is None:
            raise ValueError("point must be an exact scalar or infinity")
        if (str(self.point) in {"oo", "-oo"}) == (self.direction is not None):
            raise ValueError("finite points require direction and infinity forbids it")
        return self


class AsymptoticQuery(QueryBase):
    kind: Literal["asymptotic"] = "asymptotic"
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("variable")
    @classmethod
    def ordinary_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable

    point: str | int
    direction: Literal["left", "right", "both"] | None = None
    order: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def valid_point(self) -> "AsymptoticQuery":
        if isinstance(self.point, int) and abs(self.point) > 9_007_199_254_740_991:
            raise ValueError("numeric point must be a JavaScript-safe integer")
        if str(self.point) not in {"oo", "-oo"} and parse_exact_scalar(str(self.point)) is None:
            raise ValueError("point must be an exact scalar or infinity")
        if (str(self.point) in {"oo", "-oo"}) == (self.direction is not None):
            raise ValueError("finite points require direction and infinity forbids it")
        return self


QueryRequest = Annotated[
    EquivalenceQuery | ClosedFormQuery | PropertiesQuery | LimitQuery | AsymptoticQuery,
    Field(discriminator="kind"),
]


type ResolvedTarget = Annotated[
    ExpressionTarget | EquationTarget | DerivedTarget, Field(discriminator="kind")
]


class QueryAnswer(StructuredModel):
    check: PropertyCheck | None = None
    conclusion: Literal[
        "proved", "proved_under_assumptions", "disproved", "unresolved", "inapplicable"
    ]
    conditions: tuple[str, ...] = Field(default=(), max_length=256)
    assumptions_used: tuple["RelationshipUse", ...] = Field(default=(), max_length=128)
    relevant_unsupported_assumptions: tuple[str, ...] = Field(default=(), max_length=128)
    blockers: tuple[str, ...] = Field(default=(), max_length=128)
    evidence: QueryEvidence | None = None
    derived_candidates: tuple[DerivedCandidate, ...] = Field(default=(), max_length=32)
    constraint_uses: tuple["ConstraintUse", ...] = ()

    @model_validator(mode="after")
    def terminal_shape(self) -> "QueryAnswer":
        bounded = (*self.conditions, *self.relevant_unsupported_assumptions, *self.blockers)
        if any(not value or len(value) > 4096 for value in bounded):
            raise ValueError("query qualification strings must be nonempty and bounded")
        if self.conclusion in {"unresolved", "inapplicable"} and self.derived_candidates:
            raise ValueError("unresolved and inapplicable answers cannot carry candidates")
        return self


class QueryResultCommon(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: ResolvedTarget

    @field_validator("name")
    @classmethod
    def ordinary_name(cls, name: str) -> str:
        if name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return name

    normalized_target: "Interpretation | None"
    summary: str = Field(min_length=1, max_length=4096)
    answers: tuple[QueryAnswer, ...]

    @model_validator(mode="after")
    def derived_target_nullability(self) -> "QueryResultCommon":
        unavailable = False
        if (
            isinstance(self.target, DerivedTarget)
            and self.answers
            and all(answer.conclusion == "inapplicable" for answer in self.answers)
        ):
            prefix = f"derived target source {self.target.query} concluded "
            conclusions = tuple(
                tuple(
                    blocker.removeprefix(prefix)
                    for blocker in answer.blockers
                    if blocker.startswith(prefix)
                )
                for answer in self.answers
            )
            unavailable = (
                all(len(items) == 1 for items in conclusions)
                and len({items[0] for items in conclusions}) == 1
                and conclusions[0][0]
                in {
                    "proved",
                    "proved_under_assumptions",
                    "disproved",
                    "unresolved",
                    "inapplicable",
                }
            )
        if (self.normalized_target is None) != unavailable:
            raise ValueError("normalized target is null only for an unavailable derived target")
        return self


class EquivalenceResult(QueryResultCommon):
    kind: Literal["equivalence"] = "equivalence"

    @model_validator(mode="after")
    def exact_answer(self) -> "EquivalenceResult":
        _validate_query_answers(self.answers, None, {"identity", "counterexample"})
        return self


class ClosedFormResult(QueryResultCommon):
    kind: Literal["closed_form"] = "closed_form"

    @model_validator(mode="after")
    def exact_answer(self) -> "ClosedFormResult":
        _validate_query_answers(self.answers, None, {"closed_form"})
        return self


class PropertiesResult(QueryResultCommon):
    kind: Literal["properties"] = "properties"

    @model_validator(mode="after")
    def property_answers(self) -> "PropertiesResult":
        if not self.answers or any(answer.check is None for answer in self.answers):
            raise ValueError("properties results require checked answers")
        checks = tuple(
            answer.check.model_dump_json() for answer in self.answers if answer.check is not None
        )
        if len(checks) != len(set(checks)):
            raise ValueError("properties result checks must be unique")
        if any(
            answer.evidence is not None and answer.evidence.kind != "property"
            for answer in self.answers
        ):
            raise ValueError("properties results require property evidence")
        return self


class LimitResult(QueryResultCommon):
    kind: Literal["limit"] = "limit"

    @model_validator(mode="after")
    def exact_answer(self) -> "LimitResult":
        _validate_query_answers(self.answers, None, {"limit"})
        return self


class AsymptoticResult(QueryResultCommon):
    kind: Literal["asymptotic"] = "asymptotic"

    @model_validator(mode="after")
    def exact_answer(self) -> "AsymptoticResult":
        _validate_query_answers(self.answers, None, {"asymptotic"})
        return self


def _validate_query_answers(
    answers: tuple[QueryAnswer, ...], check: None, evidence_kinds: set[str]
) -> None:
    if len(answers) != 1 or answers[0].check is not check:
        raise ValueError("query result requires exactly one unchecked answer")
    if answers[0].evidence is not None and answers[0].evidence.kind not in evidence_kinds:
        raise ValueError("query evidence kind does not match result kind")


type QueryResult = Annotated[
    EquivalenceResult | ClosedFormResult | PropertiesResult | LimitResult | AsymptoticResult,
    Field(discriminator="kind"),
]
