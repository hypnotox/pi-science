# ruff: noqa: E501
# pyright: reportPrivateUsage=false
import re
from typing import Literal

from py_science.formula.contracts._base import StructuredModel
from py_science.formula.contracts.common import (
    _NAME_PATTERN,
    MAX_ASSUMPTIONS,
    MAX_DEFINITIONS,
    MAX_EQUATIONS,
    MAX_FORMULA_BYTES,
    MAX_FUNCTIONS,
    MAX_GENERATED_SCENARIO_RESULTS,
    MAX_NAME_LENGTH,
    MAX_PRIMITIVE_COSTS,
    MAX_SCENARIOS,
    MAX_VARIABLES,
    Assumption,
    DirectedDefinition,
    EquationRequest,
    EquationTarget,
    FormulaSyntax,
    FunctionDefinition,
    PrimitiveCost,
    Scenario,
    VariableDeclaration,
    _require_unique,
    _validate_output_identities,
)
from py_science.formula.contracts.goals import (
    BoundedGoalSearchPolicy,
    GoalSpec,
    VerifierBackedProofPolicy,
)
from py_science.formula.contracts.queries import (
    AsymptoticQuery,
    ClosedFormQuery,
    DerivedTarget,
    EquivalenceQuery,
    LimitQuery,
    PropertiesQuery,
    QueryRequest,
)
from pydantic import Field, model_validator


class AnalysisRequest(StructuredModel):
    syntax: FormulaSyntax
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    outputs: tuple[str, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    scenarios: tuple[Scenario, ...] = Field(default=(), max_length=MAX_SCENARIOS)
    queries: tuple[QueryRequest, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def validate_request(self) -> "AnalysisRequest":
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        if len(self.variables) > MAX_VARIABLES:
            raise ValueError("variable collection exceeds its bound")
        if any(
            name == "oo" or len(name) > MAX_NAME_LENGTH or re.fullmatch(_NAME_PATTERN, name) is None
            for name in self.variables
        ):
            raise ValueError("variable names must be ordinary identifiers")
        _require_unique((equation.name for equation in self.equations), "equation names")
        _validate_output_identities(self.expression, self.equations, self.outputs, required=False)
        _require_unique((function.name for function in self.functions), "function names")
        _require_unique((cost.name for cost in self.primitive_costs), "primitive cost names")
        definition_names = {function.name for function in self.functions}
        cost_names = {cost.name for cost in self.primitive_costs}
        if definition_names & cost_names:
            raise ValueError("a function cannot have both a definition and primitive work")
        callable_names = definition_names | cost_names
        if {"Eq", "Sum", "Max", "cardinality", "oo"} & callable_names or any(
            name.startswith("C_") for name in callable_names
        ):
            raise ValueError(
                "Eq, Sum, Max, cardinality, and C_ names are reserved mathematical constructs"
            )
        _require_unique((item.name for item in self.assumptions), "assumption names")
        _require_unique(
            (item.variable for item in self.definitions), "directed definition variables"
        )
        _require_unique((item.name for item in self.scenarios), "scenario names")
        _require_unique((item.name for item in self.queries), "query names")
        if (
            sum(
                len(item.comparison.encode("utf-8")) if isinstance(item, EquivalenceQuery) else 0
                for item in self.queries
            )
            > MAX_FORMULA_BYTES
        ):
            raise ValueError("query source exceeds its aggregate bound")
        for position, item in enumerate(self.queries):
            if self.expression is not None and isinstance(item.target, EquationTarget):
                raise ValueError("single-expression queries must omit equation target")
            if self.equations and item.target is None:
                raise ValueError("system queries require a named equation target")
            if isinstance(item.target, DerivedTarget):
                if not isinstance(
                    item, (EquivalenceQuery, PropertiesQuery, LimitQuery, AsymptoticQuery)
                ):
                    raise ValueError(
                        f"queries[{position}].target: derived targets require equivalence, properties, limit, or asymptotic"
                    )
                earlier = next(
                    (
                        source
                        for source in self.queries[:position]
                        if source.name == item.target.query
                    ),
                    None,
                )
                if earlier is None:
                    raise ValueError(
                        f"queries[{position}].target: derived query must reference an earlier query"
                    )
                if not isinstance(earlier, ClosedFormQuery):
                    raise ValueError(
                        f"queries[{position}].target: derived source must be a closed_form query"
                    )
        for item in self.queries:
            if isinstance(item, (LimitQuery, AsymptoticQuery)):
                infinity = str(item.point) in {"oo", "-oo"}
                if infinity == (item.direction is not None):
                    raise ValueError("finite points require direction and infinity forbids it")
        generated_results = 0
        for scenario in self.scenarios:
            population = 1
            for values in scenario.choices.values():
                population *= len(values)
            generated_results += population
        if generated_results > MAX_GENERATED_SCENARIO_RESULTS:
            raise ValueError("request generated scenario-result population exceeds its bound")
        return self


class OptimizeRequest(StructuredModel):
    """One explicit goal-driven optimization operation."""

    syntax: FormulaSyntax
    operation: Literal["optimize"]
    expression: str | None = None
    equations: tuple[EquationRequest, ...] = Field(default=(), max_length=MAX_EQUATIONS)
    variables: dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: tuple[FunctionDefinition, ...] = Field(default=(), max_length=MAX_FUNCTIONS)
    primitive_costs: tuple[PrimitiveCost, ...] = Field(default=(), max_length=MAX_PRIMITIVE_COSTS)
    assumptions: tuple[Assumption, ...] = Field(default=(), max_length=MAX_ASSUMPTIONS)
    definitions: tuple[DirectedDefinition, ...] = Field(default=(), max_length=MAX_DEFINITIONS)
    goal: GoalSpec
    search: BoundedGoalSearchPolicy
    proof: VerifierBackedProofPolicy
    projection_limit: int = Field(ge=1, le=16)

    @model_validator(mode="after")
    def request_shape(self) -> "OptimizeRequest":
        if (self.expression is None) != bool(self.equations):
            raise ValueError("provide exactly one expression or a nonempty equation list")
        AnalysisRequest.model_validate(
            {
                "syntax": self.syntax,
                "expression": self.expression,
                "equations": self.equations,
                "variables": self.variables,
                "functions": self.functions,
                "primitive_costs": self.primitive_costs,
                "assumptions": self.assumptions,
                "definitions": self.definitions,
            }
        )
        return self
