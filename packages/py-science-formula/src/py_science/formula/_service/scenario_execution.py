# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Service-owned scenario specialization."""

from __future__ import annotations

from itertools import product

from py_science.formula._analysis.computation import (
    _indexed_value_names,
    _scenario_literal,
    _symbol_names,
    _value_names,
)
from py_science.formula._analysis.retained import Knowledge, ParsedEquation, PreparedScenarioState
from py_science.formula.expressions import Expression, substitute
from py_science.formula.models import (
    EffectiveIndexDomain,
    EquationEffectiveDomains,
    IntervalResult,
    MathematicalDomain,
    RelationshipUse,
    ScenarioResult,
)
from py_science.formula.sympy_backend import is_nondecreasing_polynomial, polynomial_degree, render
from py_science.formula.work import (
    MAX_WORK_NODES,
    WorkRenderBudget,
    map_analysis,
    render_work,
    simplify_constants,
    substitute_analysis,
)


def _topological(edges: dict[str, set[str]]) -> list[str] | None:
    pending = {name: set(dependencies) for name, dependencies in edges.items()}
    ordered: list[str] = []
    while pending:
        ready = sorted(name for name, dependencies in pending.items() if not dependencies)
        if not ready:
            return None
        ordered.extend(ready)
        for name in ready:
            pending.pop(name)
        ready_set = set(ready)
        for dependencies in pending.values():
            dependencies.difference_update(ready_set)
    return ordered


def _resolved_knowledge_definitions(knowledge: Knowledge) -> dict[str, Expression]:
    replacements: dict[str, Expression] = {}
    for definition in knowledge.definitions:
        replacements[definition.name] = substitute(
            definition.expression, replacements, max_nodes=MAX_WORK_NODES
        )
    return replacements


def _compose_replacements(
    base: dict[str, Expression],
    overrides: dict[str, Expression],
) -> dict[str, Expression]:
    composed = dict(overrides)
    for name, expression in base.items():
        composed[name] = substitute(expression, composed, max_nodes=MAX_WORK_NODES)
    return composed


def scenario_results(
    prepared: PreparedScenarioState, budget: WorkRenderBudget
) -> tuple[ScenarioResult, ...]:
    """Specialize validated scenario state without reparsing request definitions."""
    general = prepared.general_analysis.as_work_analysis()
    general_relationships = prepared.general_relationships
    knowledge = prepared.knowledge
    equations = prepared.equations
    results: list[ScenarioResult] = []
    global_replacements = _resolved_knowledge_definitions(knowledge)
    declared = set(prepared.variable_domains)
    indexed_values = _indexed_value_names(general.total_work)
    for scenario in prepared.scenarios:
        treated = (
            set(scenario.fixed)
            | set(scenario.choices)
            | set(scenario.definitions)
            | set(scenario.asymptotic)
            | set(scenario.bounds)
        )
        unresolved: set[str] = set(general.unresolved)
        qualifications = ["exact general symbolic work preserved"]
        indexed_treatments = (
            set(scenario.fixed) | set(scenario.choices) | set(scenario.definitions)
        ) & indexed_values
        if indexed_treatments:
            unresolved.add(
                "scalar substitution is unsupported for indexed variables: "
                + ", ".join(sorted(indexed_treatments))
            )
        unknown_treatments = treated - declared
        if unknown_treatments:
            unresolved.add(
                "scenario treats undeclared variables: " + ", ".join(sorted(unknown_treatments))
            )
        scenario_fixed: dict[str, Expression] = {
            name: _scenario_literal(value)
            for name, value in scenario.fixed.items()
            if name not in indexed_values
        }
        replacements = _compose_replacements(global_replacements, scenario_fixed)
        relationships: list[RelationshipUse] = []
        parsed_definitions = dict(scenario.definitions)
        definition_qualifications = dict(scenario.definition_qualifications)
        definition_names = set(parsed_definitions)
        graph = {
            name: _symbol_names(parsed) & definition_names
            for name, (_, parsed) in parsed_definitions.items()
        }
        definition_order = _topological(graph) or ()
        definition_provenance: dict[str, set[str]] = {}
        used_definitions: set[str] = set()
        specialized = substitute_analysis(general, replacements)
        for name in definition_order:
            _, parsed = parsed_definitions[name]
            dependencies = _symbol_names(parsed) & set(definition_provenance)
            value = substitute(parsed, replacements, max_nodes=MAX_WORK_NODES)
            replacements[name] = value
            definition_provenance[name] = {name}.union(
                *(definition_provenance[dependency] for dependency in dependencies)
            )
            updated = substitute_analysis(specialized, {name: value})
            if updated != specialized:
                used_definitions.update(definition_provenance[name])
            specialized = updated
        for name in definition_order:
            source, _ = parsed_definitions[name]
            qualification = definition_qualifications.get(name)
            if name not in used_definitions:
                continue
            relationships.append(
                RelationshipUse(
                    name=f"derived:{name}",
                    relationship=f"{name} = {source}",
                )
            )
            if qualification is not None:
                unresolved.add(qualification)
        specialized = map_analysis(specialized, simplify_constants)
        expression = specialized.total_work
        relevant = _value_names(expression) & declared
        substituted_work = render_work(expression, budget)
        choice_work: dict[str, str] = {}
        choice_replacements: dict[str, dict[str, Expression]] = {}
        if scenario.fixed and not (set(scenario.fixed) & indexed_values):
            qualifications.append("fixed values substituted exactly")
        choice_names = sorted(scenario.choices)
        choice_values = [scenario.choices[name] for name in choice_names]
        if choice_names:
            for values in product(*choice_values):
                selected = dict(zip(choice_names, values, strict=True))
                value = simplify_constants(
                    substitute(
                        expression,
                        {name: _scenario_literal(item) for name, item in selected.items()},
                        max_nodes=MAX_WORK_NODES,
                    )
                )
                key = ",".join(f"{name}={selected[name]}" for name in choice_names)
                choice_work[key] = render_work(value, budget)
                choice_replacements[key] = {
                    **replacements,
                    **{name: _scenario_literal(item) for name, item in selected.items()},
                }
        if scenario.choices and not (set(scenario.choices) & indexed_values):
            qualifications.append("finite choices substituted exactly")
        asymptotic: str | None = None
        if len(scenario.asymptotic) > 1:
            unresolved.add("multivariate asymptotic dominance is unsupported")
        elif scenario.asymptotic:
            variable = scenario.asymptotic[0]
            domain = prepared.variable_domains.get(variable)
            untreated = relevant - treated
            if variable in indexed_values:
                unresolved.add(
                    f"asymptotic treatment for indexed variable {variable} is unsupported"
                )
            elif untreated:
                unresolved.add(
                    "untreated symbols block asymptotic classification: "
                    + ", ".join(sorted(untreated))
                )
            elif domain not in {
                MathematicalDomain.NONNEGATIVE_INTEGER,
                MathematicalDomain.POSITIVE_INTEGER,
                MathematicalDomain.POSITIVE_REAL,
            }:
                unresolved.add(f"asymptotic variable {variable} lacks a nonnegative domain")
            else:
                assert domain is not None
                degree = polynomial_degree(expression, variable)
                if degree is None or not is_nondecreasing_polynomial(expression, variable):
                    unresolved.add(f"asymptotic classification for {variable} is unsupported")
                else:
                    asymptotic = (
                        "Theta(1)"
                        if degree == 0
                        else f"Theta({variable}{'**' + str(degree) if degree != 1 else ''})"
                    )
                    relationships.append(
                        RelationshipUse(
                            name=f"domain:{variable}",
                            relationship=f"{variable} in {domain.value}",
                        )
                    )
                    qualifications.append(
                        "univariate polynomial asymptotic classification uses the declared domain"
                    )
        interval: IntervalResult | None = None
        if scenario.bounds:
            if len(scenario.bounds) != 1:
                unresolved.add("multivariate interval reasoning is unsupported")
            else:
                variable, bound = next(iter(scenario.bounds.items()))
                untreated = relevant - treated
                if variable in indexed_values:
                    unresolved.add(
                        f"interval treatment for indexed variable {variable} is unsupported"
                    )
                elif untreated:
                    unresolved.add(
                        "untreated symbols block interval reasoning: "
                        + ", ".join(sorted(untreated))
                    )
                elif not is_nondecreasing_polynomial(expression, variable):
                    unresolved.add(f"monotonic interval relationship for {variable} is unproved")
                else:
                    lower = simplify_constants(
                        substitute(
                            expression,
                            {variable: _scenario_literal(bound.lower)},
                            max_nodes=MAX_WORK_NODES,
                        )
                    )
                    upper = simplify_constants(
                        substitute(
                            expression,
                            {variable: _scenario_literal(bound.upper)},
                            max_nodes=MAX_WORK_NODES,
                        )
                    )
                    lower_work = render_work(lower, budget)
                    upper_work = render_work(upper, budget)
                    interval = IntervalResult(
                        lower=str(bound.lower),
                        upper=str(bound.upper),
                        lower_inclusive=bound.lower_inclusive,
                        upper_inclusive=bound.upper_inclusive,
                        lower_work=lower_work,
                        upper_work=upper_work,
                        infimum=lower_work,
                        supremum=upper_work,
                        infimum_attained=bound.lower_inclusive,
                        supremum_attained=bound.upper_inclusive,
                    )
                    relationships.append(
                        RelationshipUse(
                            name=f"bound:{variable}",
                            relationship=(
                                f"{bound.lower} "
                                f"{'<=' if bound.lower_inclusive else '<'} {variable} "
                                f"{'<=' if bound.upper_inclusive else '<'} {bound.upper}"
                            ),
                        )
                    )
                    qualifications.append(
                        "interval endpoints use a proven nondecreasing univariate polynomial"
                    )
        effective_domains = _specialized_effective_domains(equations, replacements)
        choice_effective_domains: dict[str, tuple[EquationEffectiveDomains, ...]] = {}
        if choice_work:
            for key in choice_work:
                # Choice keys are canonical and this result shape intentionally uses
                # exactly the same key population as choice_work.
                choice_effective_domains[key] = _specialized_effective_domains(
                    equations, choice_replacements[key]
                )
        results.append(
            ScenarioResult(
                name=scenario.name,
                substituted_work=substituted_work,
                choice_work=choice_work,
                asymptotic=asymptotic,
                interval=interval,
                substitutions={
                    name: render_work(replacements[name], budget)
                    for name in sorted(
                        set(scenario.fixed) | set(scenario.definitions)
                    )
                    if name in replacements
                },
                relationships_used=(*general_relationships, *relationships),
                qualifications=tuple(qualifications),
                unresolved=tuple(sorted(unresolved)),
                effective_domains=() if choice_work else effective_domains,
                choice_effective_domains=choice_effective_domains,
            )
        )
    return tuple(results)


def _specialized_effective_domains(
    equations: tuple[ParsedEquation, ...], replacements: dict[str, Expression]
) -> tuple[EquationEffectiveDomains, ...]:
    """Render scenario-specialized analyzer domains without reparsing input text."""
    result: list[EquationEffectiveDomains] = []
    for equation in equations:
        result.append(
            EquationEffectiveDomains(
                equation=equation.name,
                domains=tuple(
                    EffectiveIndexDomain(
                        index=domain.index,
                        lower=render(
                            substitute(domain.lower, replacements, max_nodes=MAX_WORK_NODES)
                        ).sympy,
                        upper=render(
                            substitute(domain.upper, replacements, max_nodes=MAX_WORK_NODES)
                        ).sympy,
                    )
                    for domain in equation.output_domains
                ),
            )
        )
    return tuple(result)
