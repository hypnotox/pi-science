from __future__ import annotations

import ast
import importlib
from pathlib import Path

import py_science.formula as formula
from py_science.formula import models

EXPECTED_PUBLIC_EXPORTS = frozenset(
    {
        "AnalysisError",
        "AnalysisErrorCode",
        "AnalysisFailure",
        "AnalysisOutcome",
        "AnalysisRequest",
        "AnalysisSuccess",
        "Assumption",
        "AsymptoticEvidence",
        "AsymptoticQuery",
        "AsymptoticRemainder",
        "AsymptoticResult",
        "CandidateAnalysisReport",
        "CandidateComparisonOutcome",
        "CandidateComparisonRequest",
        "CandidateComparisonSuccess",
        "CandidateComputation",
        "CandidateOutputComparison",
        "CandidateOutputMapping",
        "CandidateTargetReference",
        "CandidateWorkComparison",
        "ClosedFormEvidence",
        "ClosedFormQuery",
        "ClosedFormResult",
        "ConstraintUse",
        "CounterexampleEvidence",
        "DerivedCandidate",
        "DerivedTarget",
        "DirectWorkApplicability",
        "DirectedDefinition",
        "DomainConstraint",
        "DominanceAnalysisOutcome",
        "DominanceAnalysisRequest",
        "DominanceAnalysisSuccess",
        "DominanceCell",
        "DominanceEvidence",
        "DominanceExclusion",
        "DominanceIntegerRangeCell",
        "DominanceIntervalCell",
        "DominancePointCell",
        "DominanceRange",
        "DominanceTerm",
        "EffectiveIndexDomain",
        "EquationEffectiveDomains",
        "EquationReport",
        "EquationRequest",
        "EquationTarget",
        "EquivalenceQuery",
        "EquivalenceResult",
        "ExactRational",
        "ExactScenarioScalar",
        "ExpressionTarget",
        "FormulaSyntax",
        "FunctionDefinition",
        "IdentityEvidence",
        "IndexDomain",
        "InfinityLiteral",
        "Interpretation",
        "IntervalBound",
        "IntervalResult",
        "LimitEvidence",
        "LimitQuery",
        "LimitResult",
        "MathematicalDomain",
        "OperationCounts",
        "OptimizationCandidate",
        "OptimizationConfig",
        "OptimizationFailure",
        "OptimizationIntermediate",
        "OptimizationObjective",
        "OptimizationOccurrence",
        "OptimizationOrdering",
        "OptimizationPlan",
        "OptimizationReport",
        "OptimizationSuccess",
        "OptimizationSuggestion",
        "OptimizationTarget",
        "OptimizationTraceStep",
        "OptimizationTransformation",
        "OptimizeOutcome",
        "OptimizeRequest",
        "PrimitiveCost",
        "PropertiesQuery",
        "PropertiesResult",
        "PropertyCheck",
        "PropertyEvidence",
        "QueryAnswer",
        "QueryResult",
        "RationalLiteral",
        "RelationshipUse",
        "ReuseReport",
        "Scenario",
        "ScenarioResult",
        "SignPropertyCheck",
        "SourceLocation",
        "SourceReference",
        "SourceSpan",
        "SymbolicOperationCounts",
        "SystemReport",
        "UnitWorkObjective",
        "VariableDeclaration",
        "VariablePropertyCheck",
        "WeightedOperationWeights",
        "WeightedOperationsObjective",
        "analyze",
        "analyze_dominance",
        "compare_candidates",
        "optimize",
        "parse_exact_scalar",
        "render_exact",
    }
)


def test_public_formula_root_exports_are_complete_unique_and_importable() -> None:
    assert frozenset(formula.__all__) == EXPECTED_PUBLIC_EXPORTS
    assert len(formula.__all__) == len(EXPECTED_PUBLIC_EXPORTS)
    assert all(getattr(formula, name) is not None for name in formula.__all__)


CONTRACT_OWNERS = {
    "_base": {"StructuredModel"},
    "common": {
        "MAX_NAME_LENGTH",
        "MAX_FORMULA_BYTES",
        "MAX_EQUATIONS",
        "MAX_FUNCTIONS",
        "MAX_VARIABLES",
        "MAX_PRIMITIVE_COSTS",
        "MAX_ASSUMPTIONS",
        "MAX_DEFINITIONS",
        "MAX_SCENARIOS",
        "MAX_TREATMENTS_PER_SCENARIO",
        "MAX_CHOICES_PER_VARIABLE",
        "MAX_GENERATED_SCENARIO_RESULTS",
        "MAX_SCENARIO_INTEGER_BITS",
        "ExactScenarioScalar",
        "MAX_DOMAINS_PER_EQUATION",
        "MAX_CONSTRAINTS_PER_EQUATION",
        "MAX_PARAMETERS",
        "_NAME_PATTERN",
        "FormulaSyntax",
        "MathematicalDomain",
        "IndexDomain",
        "VariableDeclaration",
        "Assumption",
        "DirectedDefinition",
        "_exact_scenario_scalar",
        "IntervalBound",
        "Scenario",
        "DomainConstraint",
        "EquationRequest",
        "FunctionDefinition",
        "PrimitiveCost",
        "_validate_parameters",
        "EquationTarget",
        "ExpressionTarget",
        "DerivedTarget",
        "Interpretation",
        "OperationCounts",
        "SymbolicOperationCounts",
        "DirectWorkApplicability",
        "EffectiveIndexDomain",
        "ConstraintUse",
        "EquationEffectiveDomains",
        "RelationshipUse",
        "IntervalResult",
        "_validate_output_identities",
        "_require_unique",
    },
    "evidence": {
        "DerivedCandidate",
        "IdentityEvidence",
        "CounterexampleEvidence",
        "ClosedFormEvidence",
        "PropertyEvidence",
        "BoundedQueryText",
        "LimitEvidence",
        "AsymptoticRemainder",
        "AsymptoticEvidence",
        "QueryEvidence",
    },
    "queries": {
        "VariablePropertyCheck",
        "SignPropertyCheck",
        "PropertyCheck",
        "QueryBase",
        "EquivalenceQuery",
        "ClosedFormQuery",
        "PropertiesQuery",
        "LimitQuery",
        "AsymptoticQuery",
        "QueryRequest",
        "ResolvedTarget",
        "QueryAnswer",
        "QueryResultCommon",
        "EquivalenceResult",
        "ClosedFormResult",
        "PropertiesResult",
        "LimitResult",
        "AsymptoticResult",
        "_validate_query_answers",
        "QueryResult",
    },
    "optimization": {
        "UnitWorkObjective",
        "WeightedOperationWeights",
        "WeightedOperationsObjective",
        "OptimizationObjective",
        "AlgorithmicOptimizationFamily",
        "OptimizationConfig",
        "OptimizationCandidate",
        "OptimizationTarget",
        "OptimizationOccurrence",
        "OptimizationIntermediate",
        "OptimizationTransformation",
        "OptimizationKind",
        "OptimizationTier",
        "OPTIMIZATION_FAMILY_TIERS",
        "OptimizationSuggestion",
        "OptimizationOrdering",
        "OptimizationTraceStep",
        "OptimizationPlan",
        "OptimizationFailure",
        "_validate_optimization_plan_population",
        "OptimizationSuccess",
        "OptimizeOutcome",
        "OptimizationReport",
    },
    "requests": {"AnalysisRequest", "OptimizeRequest"},
    "reports": {
        "AnalysisErrorCode",
        "SourceLocation",
        "SourceSpan",
        "SourceReference",
        "AnalysisError",
        "EquationReport",
        "ScenarioResult",
        "ReuseReport",
        "SystemReport",
        "AnalysisSuccess",
        "AnalysisFailure",
        "AnalysisOutcome",
        "_validate_direct_work_variant",
    },
    "comparison": {
        "CandidateComputation",
        "CandidateTargetReference",
        "CandidateOutputMapping",
        "CandidateComparisonRequest",
        "CandidateAnalysisReport",
        "CandidateOutputComparison",
        "CandidateWorkComparison",
        "CandidateComparisonSuccess",
        "CandidateComparisonOutcome",
    },
    "dominance": {
        "DominanceRange",
        "DominanceAnalysisRequest",
        "DominanceTerm",
        "DominanceIntervalCell",
        "DominancePointCell",
        "DominanceIntegerRangeCell",
        "DominanceCell",
        "DominanceExclusion",
        "DominanceEvidence",
        "_dominance_exact_sort_key",
        "_dominance_cell_bounds",
        "_validate_dominance_cell_order",
        "_range_bounds",
        "_dominance_bounds_within",
        "_validate_complete_dominance_coverage",
        "DominanceAnalysisSuccess",
        "DominanceAnalysisOutcome",
    },
}


def test_contract_owners_and_compatibility_facades_preserve_object_identity() -> None:
    for module_name, names in CONTRACT_OWNERS.items():
        module = importlib.import_module(f"py_science.formula.contracts.{module_name}")
        for name in names:
            defining_object = getattr(module, name)
            assert getattr(models, name) is defining_object, name
            if name in EXPECTED_PUBLIC_EXPORTS:
                assert getattr(formula, name) is defining_object, name


def test_models_wildcard_surface_excludes_private_compatibility_aliases() -> None:
    expected = {
        name
        for names in CONTRACT_OWNERS.values()
        for name in names
        if not name.startswith("_")
    }
    assert set(models.__all__) == expected


CONTRACT_DEPENDENCIES: dict[str, set[str]] = {
    "_base": set(),
    "common": {"_base"},
    "evidence": {"_base", "common"},
    "queries": {"_base", "common", "evidence"},
    "optimization": {"_base", "common", "evidence"},
    "requests": {"_base", "common", "queries", "optimization"},
    "reports": {"_base", "common", "queries", "optimization"},
    "comparison": {"_base", "common", "evidence", "queries", "requests", "reports"},
    "dominance": {"_base", "common", "requests", "reports"},
}
FORBIDDEN_CONTRACT_IMPORTS = (
    "pi_science",
    "sympy",
    "py_science.formula.models",
    "py_science.formula.optimization",
    "py_science.formula.optimizer",
    "py_science.formula.parser",
    "py_science.formula.service",
)


def _contract_import_violations(module_name: str, source: str) -> list[str]:
    violations: list[str] = []
    formula_root = "py_science.formula"
    contracts_root = f"{formula_root}.contracts"
    prefix = f"{contracts_root}."
    for node in ast.walk(ast.parse(source)):
        imported: list[str] = []
        dependencies: set[str] = set()
        if isinstance(node, ast.Import):
            imported = [alias.name for alias in node.names]
            for imported_name in imported:
                if imported_name.startswith(prefix):
                    dependencies.add(imported_name.removeprefix(prefix).split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            elif node.level == 1:
                base = contracts_root
                if node.module:
                    base = f"{base}.{node.module}"
            elif node.level == 2:
                base = formula_root
                if node.module:
                    base = f"{base}.{node.module}"
            else:
                base = "py_science"
            imported = [base, *(f"{base}.{alias.name}" for alias in node.names)]
            if base == contracts_root:
                violations.append(contracts_root)
                dependencies.update(alias.name for alias in node.names)
            elif base.startswith(prefix):
                dependencies.add(base.removeprefix(prefix).split(".", 1)[0])
        for imported_name in imported:
            if imported_name == formula_root or any(
                imported_name == forbidden or imported_name.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_CONTRACT_IMPORTS
            ):
                violations.append(imported_name)
        for dependency in dependencies:
            if dependency not in CONTRACT_DEPENDENCIES[module_name]:
                violations.append(f"contracts.{dependency}")
    return violations


def test_contract_import_graph_is_acyclic_and_transport_free() -> None:
    contracts = Path(models.__file__).with_name("contracts")
    for module_name in CONTRACT_DEPENDENCIES:
        source = (contracts / f"{module_name}.py").read_text()
        assert _contract_import_violations(module_name, source) == []


def test_contract_import_graph_probe_rejects_every_forbidden_edge_form() -> None:
    prohibited = (
        "import sympy",
        "import pi_science",
        "import py_science.formula",
        "import py_science.formula.contracts.dominance",
        "from py_science.formula import AnalysisRequest",
        "from py_science.formula import models",
        "from py_science.formula import optimization",
        "from py_science.formula.contracts import dominance",
        "from py_science.formula.parser import parse_expression",
        "from .. import service",
        "from ..optimizer import optimize",
        "from . import dominance",
        "from .dominance import DominanceRange",
    )
    assert all(_contract_import_violations("common", source) for source in prohibited)
