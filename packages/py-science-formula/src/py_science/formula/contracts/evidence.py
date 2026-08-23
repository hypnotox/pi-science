# pyright: reportPrivateUsage=false
import re
from typing import Annotated, Literal

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.contracts.common import (
    _NAME_PATTERN,
    MAX_NAME_LENGTH,
    Interpretation,
    OperationCounts,
)
from py_science.formula.exact_values import parse_exact_scalar, render_exact
from pydantic import Field, model_validator


class DerivedCandidate(StructuredModel):
    interpretation: "Interpretation"
    operation_counts: "OperationCounts"


class IdentityEvidence(StructuredModel):
    kind: Literal["identity"] = "identity"
    statement: str = Field(min_length=1, max_length=4096)


class CounterexampleEvidence(StructuredModel):
    kind: Literal["counterexample"] = "counterexample"
    substitutions: dict[str, str] = Field(max_length=256)
    target_value: str = Field(min_length=1, max_length=4096)
    comparison_value: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def canonical_substitutions(self) -> "CounterexampleEvidence":
        if any(
            len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None or name == "oo"
            for name in self.substitutions
        ):
            raise ValueError("counterexample substitution names must be ordinary identifiers")
        parsed = (parse_exact_scalar(value) for value in self.substitutions.values())
        if any(
            item is None or render_exact(item) != value
            for item, value in zip(parsed, self.substitutions.values(), strict=True)
        ):
            raise ValueError("counterexample substitutions must be canonical exact scalars")
        for value in (self.target_value, self.comparison_value):
            exact = parse_exact_scalar(value)
            if exact is None or render_exact(exact) != value:
                raise ValueError("counterexample values must be canonical exact scalars")
        return self


class ClosedFormEvidence(StructuredModel):
    kind: Literal["closed_form"] = "closed_form"
    verification: Literal["finite_antidifference", "infinite_partial_sum"]
    statement: str = Field(min_length=1, max_length=4096)


class PropertyEvidence(StructuredModel):
    kind: Literal["property"] = "property"
    value: str = Field(min_length=1, max_length=4096)
    intervals: tuple[str, ...] = Field(default=(), max_length=256)


type BoundedQueryText = Annotated[str, Field(min_length=1, max_length=4096)]


class LimitEvidence(StructuredModel):
    kind: Literal["limit"] = "limit"
    exists: bool
    value: BoundedQueryText | None
    left: BoundedQueryText | None
    right: BoundedQueryText | None


class AsymptoticRemainder(StructuredModel):
    local_parameter: str = Field(min_length=1, max_length=4096)
    exponent: int
    normalized_big_o: str = Field(min_length=1, max_length=4096)


class AsymptoticEvidence(StructuredModel):
    kind: Literal["asymptotic"] = "asymptotic"
    statement: str = Field(min_length=1, max_length=4096)
    remainder: AsymptoticRemainder | None


type QueryEvidence = Annotated[
    IdentityEvidence
    | CounterexampleEvidence
    | ClosedFormEvidence
    | PropertyEvidence
    | LimitEvidence
    | AsymptoticEvidence,
    Field(discriminator="kind"),
]
