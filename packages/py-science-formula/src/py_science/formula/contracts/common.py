# pyright: reportPrivateUsage=false, reportUnusedFunction=false
import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Any, Literal, cast

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.exact_values import parse_exact_scalar, render_exact
from pydantic import Field, ValidationError, field_validator, model_validator

MAX_NAME_LENGTH = 128


MAX_FORMULA_BYTES = 65_536


MAX_EQUATIONS = 128


MAX_FUNCTIONS = 128


MAX_VARIABLES = 256


MAX_PRIMITIVE_COSTS = 128


MAX_ASSUMPTIONS = 128


MAX_DEFINITIONS = 128


MAX_SCENARIOS = 64


MAX_TREATMENTS_PER_SCENARIO = 64


MAX_CHOICES_PER_VARIABLE = 32


MAX_GENERATED_SCENARIO_RESULTS = 256


MAX_SCENARIO_INTEGER_BITS = 3_402


type ExactScenarioScalar = str | int


MAX_DOMAINS_PER_EQUATION = 32


MAX_CONSTRAINTS_PER_EQUATION = 32


MAX_PARAMETERS = 32


_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*$"


class FormulaSyntax(StrEnum):
    SYMPY = "sympy"


class MathematicalDomain(StrEnum):
    INTEGER = "integer"
    NONNEGATIVE_INTEGER = "nonnegative_integer"
    POSITIVE_INTEGER = "positive_integer"
    REAL = "real"
    POSITIVE_REAL = "positive_real"
    NONNEGATIVE_REAL = "nonnegative_real"

    @property
    def is_integer(self) -> bool:
        return self in {
            MathematicalDomain.INTEGER,
            MathematicalDomain.NONNEGATIVE_INTEGER,
            MathematicalDomain.POSITIVE_INTEGER,
        }


class IndexDomain(StructuredModel):
    lower: str
    upper: str


class VariableDeclaration(StructuredModel):
    domain: MathematicalDomain


class Assumption(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    relationship: str


class DirectedDefinition(StructuredModel):
    variable: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, variable: str) -> str:
        if variable == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return variable


def _exact_scenario_scalar(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(
            "scenario scalar must be an exact scalar string or JavaScript-safe integer"
        )
    if isinstance(value, int) and abs(value) > 9_007_199_254_740_991:
        raise ValueError("numeric scenario scalar must be a JavaScript-safe integer")
    parsed = parse_exact_scalar(str(value))
    if parsed is None:
        raise ValueError("scenario scalar must use the exact scalar grammar")
    return render_exact(parsed)


class IntervalBound(StructuredModel):
    lower: ExactScenarioScalar
    upper: ExactScenarioScalar
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    @field_validator("lower", "upper", mode="before")
    @classmethod
    def canonical_scalar(cls, value: object) -> str:
        return _exact_scenario_scalar(value)

    @model_validator(mode="after")
    def validate_order(self) -> "IntervalBound":
        lower = parse_exact_scalar(str(self.lower))
        upper = parse_exact_scalar(str(self.upper))
        assert lower is not None and upper is not None
        if (lower.numerator * upper.denominator > upper.numerator * lower.denominator) or (
            lower.numerator * upper.denominator == upper.numerator * lower.denominator
            and not (self.lower_inclusive and self.upper_inclusive)
        ):
            raise ValueError("interval bounds must define a nonempty interval")
        return self


class Scenario(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    fixed: dict[str, ExactScenarioScalar] = Field(default_factory=dict)
    choices: dict[str, tuple[ExactScenarioScalar, ...]] = Field(default_factory=dict)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    asymptotic: tuple[str, ...] = ()
    bounds: dict[str, IntervalBound] = Field(default_factory=dict)

    @field_validator("fixed", mode="before")
    @classmethod
    def canonical_fixed(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        raw = cast(dict[str, Any], values)
        return {name: _exact_scenario_scalar(value) for name, value in raw.items()}

    @field_validator("choices", mode="before")
    @classmethod
    def canonical_choices(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        raw = cast(dict[str, Any], values)
        return {
            name: tuple(_exact_scenario_scalar(value) for value in choices)
            for name, choices in raw.items()
        }

    @model_validator(mode="after")
    def validate_treatments(self) -> "Scenario":
        populations = (
            len(self.fixed)
            + len(self.choices)
            + len(self.definitions)
            + len(self.asymptotic)
            + len(self.bounds)
        )
        if populations > MAX_TREATMENTS_PER_SCENARIO:
            raise ValueError("scenario treatment collection exceeds its bound")
        names = [
            *self.fixed,
            *self.choices,
            *(item.variable for item in self.definitions),
            *self.asymptotic,
            *self.bounds,
        ]
        if any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in names
        ):
            raise ValueError("scenario variable names must be ordinary identifiers")
        if len(names) != len(set(names)):
            raise ValueError("a scenario variable may have only one treatment")
        if any(
            not values or len(values) > MAX_CHOICES_PER_VARIABLE for values in self.choices.values()
        ):
            raise ValueError("finite choices must be nonempty and within their bound")
        if any(len(values) != len(set(values)) for values in self.choices.values()):
            raise ValueError("finite choices must be unique")
        generated = 1
        for values in self.choices.values():
            generated *= len(values)
            if generated > MAX_GENERATED_SCENARIO_RESULTS:
                raise ValueError("scenario generated-result population exceeds its bound")
        return self


class DomainConstraint(StructuredModel):
    """One named, equation-local relationship tightening an output index."""

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    target: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    relationship: str = Field(min_length=1, max_length=262_144)


class EquationRequest(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    expression: str
    domains: dict[str, IndexDomain] = Field(default_factory=dict)
    constraints: tuple[DomainConstraint, ...] = Field(
        default=(), max_length=MAX_CONSTRAINTS_PER_EQUATION
    )

    @field_validator("constraints")
    @classmethod
    def validate_constraint_names(
        cls, constraints: tuple[DomainConstraint, ...]
    ) -> tuple[DomainConstraint, ...]:
        names: set[str] = set()
        for position, constraint in enumerate(constraints):
            if constraint.name in names:
                raise ValidationError.from_exception_data(
                    cls.__name__,
                    [
                        {
                            "type": "value_error",
                            "loc": (position, "name"),
                            "input": constraint.name,
                            "ctx": {
                                "error": ValueError("equation constraint names must be unique")
                            },
                        }
                    ],
                )
            names.add(constraint.name)
        return constraints

    @model_validator(mode="after")
    def validate_domains(self) -> "EquationRequest":
        if len(self.domains) > MAX_DOMAINS_PER_EQUATION:
            raise ValueError("equation domain collection exceeds its bound")
        if any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in self.domains
        ):
            raise ValueError("equation domain names must be ordinary identifiers")
        return self


class FunctionDefinition(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    parameters: tuple[str, ...] = Field(max_length=MAX_PARAMETERS)
    body: str

    @model_validator(mode="after")
    def validate_parameters(self) -> "FunctionDefinition":
        if self.name in {"oo", "Let"}:
            raise ValueError(f"{self.name} is reserved for mathematical syntax")
        _validate_parameters(self.parameters)
        return self


class PrimitiveCost(StructuredModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)
    parameters: tuple[str, ...] = Field(max_length=MAX_PARAMETERS)
    work: str

    @model_validator(mode="after")
    def validate_parameters(self) -> "PrimitiveCost":
        if self.name in {"oo", "Let"}:
            raise ValueError(f"{self.name} is reserved for mathematical syntax")
        _validate_parameters(self.parameters)
        return self


def _validate_parameters(parameters: tuple[str, ...]) -> None:
    if len(set(parameters)) != len(parameters):
        raise ValueError("function parameters must be unique")
    if any(
        parameter == "oo"
        or len(parameter) > MAX_NAME_LENGTH
        or re.fullmatch(_NAME_PATTERN, parameter) is None
        for parameter in parameters
    ):
        raise ValueError("function parameters must be ordinary identifiers")


class EquationTarget(StructuredModel):
    kind: Literal["equation"] = "equation"
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("name")
    @classmethod
    def ordinary_name(cls, name: str) -> str:
        if name == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return name


class ExpressionTarget(StructuredModel):
    kind: Literal["expression"] = "expression"


class DerivedTarget(StructuredModel):
    kind: Literal["derived"] = "derived"
    query: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, pattern=_NAME_PATTERN)

    @field_validator("query")
    @classmethod
    def ordinary_name(cls, query: str) -> str:
        if query == "oo":
            raise ValueError("oo is reserved for mathematical infinity")
        return query


class Interpretation(StructuredModel):
    normalized_sympy: str
    normalized_latex: str


class OperationCounts(StructuredModel):
    additions: int = Field(default=0, ge=0)
    subtractions: int = Field(default=0, ge=0)
    multiplications: int = Field(default=0, ge=0)
    divisions: int = Field(default=0, ge=0)
    powers: int = Field(default=0, ge=0)


class SymbolicOperationCounts(StructuredModel):
    additions: str = "0"
    subtractions: str = "0"
    multiplications: str = "0"
    divisions: str = "0"
    powers: str = "0"


type DirectWorkApplicability = Literal["finite", "not_finite"]


class EffectiveIndexDomain(StructuredModel):
    index: str
    lower: str = Field(min_length=1, max_length=4096)
    upper: str = Field(min_length=1, max_length=4096)


class ConstraintUse(StructuredModel):
    equation: str
    name: str
    target: str
    relationship: str


class EquationEffectiveDomains(StructuredModel):
    equation: str
    domains: tuple[EffectiveIndexDomain, ...] = Field(max_length=MAX_DOMAINS_PER_EQUATION)


class RelationshipUse(StructuredModel):
    name: str
    relationship: str


class IntervalResult(StructuredModel):
    lower: str
    upper: str
    lower_inclusive: bool
    upper_inclusive: bool
    lower_work: str
    upper_work: str
    infimum: str
    supremum: str
    infimum_attained: bool
    supremum_attained: bool
    conservative: bool = True


def _validate_output_identities(
    expression: str | None,
    equations: tuple[EquationRequest, ...],
    outputs: tuple[str, ...],
    *,
    required: bool,
) -> None:
    if required and not outputs:
        raise ValueError("output identities must be nonempty")
    if not outputs:
        return
    if len(set(outputs)) != len(outputs):
        raise ValueError("output identities must be unique")
    if expression is not None:
        if outputs != ("expression",):
            raise ValueError("expression output identity must be expression")
        return
    equation_names = {item.name for item in equations}
    if not set(outputs) <= equation_names:
        raise ValueError("output identities must name transformed equations")


def _require_unique(values: Iterable[str], label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"{label} must be unique")
