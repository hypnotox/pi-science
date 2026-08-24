# pyright: reportPrivateUsage=false
import ast
from pathlib import Path
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_retained_analysis_disables_optimization() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained

    retained = analyze_retained(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))

    assert not isinstance(retained, AnalysisFailure)
    assert "optimization" not in retained.success.model_dump()
    assert (
        "optimization"
        not in type(retained.success)
        .model_validate_json(retained.success.model_dump_json())
        .model_dump()
    )


def test_complete_candidate_replays_expression_local_reuse_and_neutral_removal() -> None:
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import (
        _complete_candidate,
        _generate_candidates,
        _OptimizationBudget,
    )

    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        expression="(x + 1) * (x + 1) + 0",
    )
    retained = analyze_retained(request)
    assert not isinstance(retained, AnalysisFailure)
    candidates, _ = _generate_candidates(retained, _OptimizationBudget())
    for candidate in candidates:
        if candidate.kind not in {"repeated_subexpression", "redundant_operation_removal"}:
            continue
        replayed = analyze_retained(_complete_candidate(candidate, request, retained))
        assert not isinstance(replayed, AnalysisFailure)
        assert replayed.expression is not None
        assert replayed.aggregate_analysis.total_work != retained.aggregate_analysis.total_work


def test_complete_candidate_schedule_preserves_all_kinds_and_the_tail() -> None:
    from py_science.formula.optimization import (
        _CandidateComputation,
        _complete_candidate_schedule,
    )

    kinds = (
        "repeated_subexpression",
        "repeated_call",
        "reciprocal_reuse",
        "factoring",
        "redundant_operation_removal",
        "iterator_invariant_hoisting",
        "cross_equation_sharing",
        "horner",
        "repeated_subexpression",
    )
    candidates = tuple(
        _CandidateComputation(
            kind=kind,
            target=f"target{position}",
            original=_expression("x"),
            proposed=_expression("x"),
            occurrences=(),
        )
        for position, kind in enumerate(kinds)
    )

    scheduled = _complete_candidate_schedule(candidates)

    assert len(scheduled) == 8
    assert {item.kind for item in scheduled} == set(kinds)
    assert scheduled[-1] is candidates[-1]


def test_ordinary_analysis_has_no_optimization_field_or_optimizer_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
    from py_science.formula._service import optimization as optimization_service

    monkeypatch.setattr(
        optimization_service,
        "optimize",
        lambda _request: pytest.fail("ordinary analysis dispatched optimizer"),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0"))

    assert outcome.status == "success"
    assert "optimization" not in outcome.model_dump()
    assert "optimization" not in outcome.model_dump_json()


def test_optimize_operation_returns_replayable_complete_plans() -> None:
    from goal_requests import goal_request
    from py_science.formula import (
        AnalysisRequest,
        FormulaSyntax,
        analyze,
        optimize,
    )

    request = goal_request(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x*x + x*x",
        )
    )
    result = optimize(request)

    assert result.status == "success"
    assert result.projection_limit == 16

    assert result.plans
    plan = result.plans[0]
    assert plan.candidate.syntax == FormulaSyntax.SYMPY
    assert plan.candidate.expression is not None
    assert plan.candidate.outputs == ("expression",)
    replay = analyze(AnalysisRequest.model_validate(plan.candidate.model_dump()))
    assert replay.status == "success"


def test_analysis_replay_rejects_invalid_output_identities() -> None:
    from py_science.formula import AnalysisRequest, EquationRequest, FormulaSyntax
    from pydantic import ValidationError

    equation = EquationRequest(name="a", expression="Eq(a, x)")
    payloads = (
        {"syntax": FormulaSyntax.SYMPY, "expression": "x", "outputs": ("wrong",)},
        {
            "syntax": FormulaSyntax.SYMPY,
            "equations": (equation,),
            "outputs": ("missing",),
        },
        {
            "syntax": FormulaSyntax.SYMPY,
            "equations": (equation,),
            "outputs": ("a", "a"),
        },
    )
    for payload in payloads:
        with pytest.raises(ValidationError, match="output identit"):
            AnalysisRequest.model_validate(payload)


def test_optimize_system_plan_outputs_exclude_generated_producers() -> None:
    from goal_requests import goal_request
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        OptimizationResult,
        VariableDeclaration,
        analyze,
        optimize,
    )

    result = optimize(
        goal_request(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                equations=(
                    EquationRequest(name="a", expression="Eq(a, x*x + 1)"),
                    EquationRequest(name="b", expression="Eq(b, x*x - 1)"),
                ),
                variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            ),
            projection_limit=16,
        )
    )

    assert isinstance(result, OptimizationResult)
    sharing = next(
        plan for plan in result.plans if plan.suggestion.kind == "cross_equation_sharing"
    )
    assert sharing.candidate.outputs == ("a", "b")
    assert {equation.name for equation in sharing.candidate.equations} == {
        "optimization_tmp_1",
        "a",
        "b",
    }
    replay = analyze(AnalysisRequest.model_validate(sharing.candidate.model_dump()))
    assert replay.status == "success"


def test_composed_search_v1_emits_replayable_trace() -> None:
    """A composed plan is represented by replayable parent-relative steps."""
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    outcome = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0")
    )
    assert outcome.status == "success"
    assert any(len(plan.trace) == 2 for plan in outcome.plans)


def test_composed_search_v1_trace_objectives_are_continuous_and_replayable() -> None:
    """Every local transition connects its parent objective to the final proof."""
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

    outcome = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="(x + 1)*(x + 1) + 0")
    )
    assert outcome.status == "success"
    plan = next(item for item in outcome.plans if len(item.trace) == 2)

    assert plan.trace[0].objective_before == plan.suggestion.objective_before
    assert plan.trace[-1].objective_after == plan.suggestion.objective_after
    assert plan.trace[0].objective_after == plan.trace[1].objective_before
    assert plan.trace[-1].candidate == plan.candidate
    for step in plan.trace:
        replayed = analyze(AnalysisRequest.model_validate(step.candidate.model_dump()))
        assert replayed.status == "success"


def _analyzer_boundary_violations(source: str) -> set[str]:
    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "py_science.formula.service"
            or alias.name.startswith("py_science.formula.service.")
            for alias in node.names
        ):
            violations.add("service-import")
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if (
                module == "py_science.formula.service"
                or module.startswith("py_science.formula.service.")
                or (node.level > 0 and module in {"service", ""})
                or (
                    node.level == 0
                    and module == "py_science.formula"
                    and any(alias.name == "service" for alias in node.names)
                )
            ):
                violations.add("service-import")
        if isinstance(node, ast.Global):
            violations.add("process-global-state")
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and "_RetainedAnalyzer" in ast.unparse(node.annotation):
            violations.add("process-global-state")
    report = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_optimization_result"
        ),
        None,
    )
    if report is None:
        violations.add("missing-report-entry-point")
    else:
        keyword_names = [argument.arg for argument in report.args.kwonlyargs]
        if "analyzer" not in keyword_names:
            violations.add("analyzer-not-required-keyword-only")
        else:
            position = keyword_names.index("analyzer")
            if report.args.kw_defaults[position] is not None:
                violations.add("analyzer-not-required-keyword-only")
        if any(argument.arg == "analyzer" for argument in report.args.args):
            violations.add("analyzer-not-required-keyword-only")
    return violations


def _imported_modules(source: str) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(f"{'.' * node.level}{node.module}")
    return modules


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            "from py_science.formula.service import _analyze_computation\n",
            "service-import",
        ),
        ("from .service import _analyze_computation\n", "service-import"),
        ("from py_science.formula import service\n", "service-import"),
        (
            "_fallback: _RetainedAnalyzer | None = None\n"
            "def _optimization_result(*, analyzer: _RetainedAnalyzer = _fallback):\n"
            "    return analyzer\n",
            "process-global-state",
        ),
        (
            "def _optimization_result(analyzer: _RetainedAnalyzer | None = None):\n"
            "    return analyzer\n",
            "analyzer-not-required-keyword-only",
        ),
    ),
)
def test_neutral_analyzer_dependency_probe_detects_regressions(source: str, expected: str) -> None:
    assert expected in _analyzer_boundary_violations(source)


def test_neutral_analyzer_is_explicit_and_has_no_service_or_registry_edge() -> None:
    """Replay callers receive the neutral analyzer without process-global setup."""
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula.optimization import _optimization_result
    from py_science.formula.service import _analyze_computation

    optimization_source = Path(_optimization_result.__code__.co_filename).read_text()
    formula_directory = Path(analyze_retained.__code__.co_filename).parents[1]
    comparison_source = formula_directory.joinpath("comparison.py").read_text()
    service_source = formula_directory.joinpath("service.py").read_text()

    assert _analyze_computation is analyze_retained
    assert _analyzer_boundary_violations(optimization_source) == set()
    assert "py_science.formula._analysis.computation" in _imported_modules(comparison_source)
    assert "._analysis.computation" in _imported_modules(service_source)
    assert "._service.orchestration" in _imported_modules(service_source)


def _optimizer_import_violations(source: str, module: str) -> set[str]:
    """Return forbidden optimizer dependency directions from AST imports."""
    import ast

    violations: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported = {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported = {f"{'.' * node.level}{node.module or ''}"}
            if node.level == 0:
                imported.update(alias.name for alias in node.names)
        else:
            continue
        if any(
            name == "py_science.formula.service" or name.endswith(".service") for name in imported
        ):
            violations.add("service")
        if module != "facade" and any(
            name == "py_science.formula.optimization" or name.endswith(".optimization")
            for name in imported
        ):
            violations.add("facade")
        if module != "package" and any(
            name in {"._optimization", "py_science.formula._optimization"} for name in imported
        ):
            violations.add("barrel")
    return violations


def test_optimizer_owner_import_dag_and_falsified_regressions() -> None:
    """Owners consume direct seams and cannot regain facade or service coupling."""
    from py_science.formula._optimization import canonical, objectives, replay, search, verifier
    from py_science.formula._optimization.families import repeated_structure

    sources = {
        "families": Path(repeated_structure.__file__).read_text(),
        "replay": Path(replay.__file__).read_text(),
        "verifier": Path(verifier.__file__).read_text(),
        "search": Path(search.__file__).read_text(),
        "canonical": Path(canonical.__file__).read_text(),
        "objectives": Path(objectives.__file__).read_text(),
    }
    assert all(
        _optimizer_import_violations(source, name) == set() for name, source in sources.items()
    )
    assert ".candidates" in sources["families"]
    assert ".candidates" in sources["replay"]
    assert ".replay" in sources["verifier"]
    for dependency in (".canonical", ".objectives", ".verifier", ".families"):
        assert dependency in sources["search"]
    assert _optimizer_import_violations(
        "from py_science.formula.service import analyze\n", "search"
    ) == {"service"}
    assert _optimizer_import_violations(
        "from py_science.formula.optimization import _verify_candidate\n", "search"
    ) == {"facade"}
    assert _optimizer_import_violations(
        "from py_science.formula._optimization import search\n", "search"
    ) == {"barrel"}


def _owner_import_edges(source: str, package: str) -> set[str]:
    """Resolve absolute and relative imports to package-qualified owner edges."""
    tree = ast.parse(source)
    edges: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parent = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join((*parent, *(node.module or "").split(".")))
                base = base.rstrip(".")
                edges.add(base)
                edges.update(f"{base}.{alias.name}" for alias in node.names)
            elif node.module:
                edges.add(node.module)
                edges.update(f"{node.module}.{alias.name}" for alias in node.names)
    return edges


_OPTIMIZATION_PACKAGE = "py_science.formula._optimization"
_FAMILY_PACKAGE = f"{_OPTIMIZATION_PACKAGE}.families"


_FAMILY_NAMES = frozenset(
    {
        "repeated_structure",
        "call_reuse",
        "factoring",
        "redundant_operations",
        "invariant_hoisting",
        "cross_equation_sharing",
        "horner",
        "finite_polynomial_sum",
    }
)
_FAMILY_OWNERS = frozenset(f"{_FAMILY_PACKAGE}.{name}" for name in _FAMILY_NAMES)
_OWNER_OWNERS = frozenset(
    f"{_OPTIMIZATION_PACKAGE}.{name}"
    for name in (
        "budgets",
        "candidates",
        "canonical",
        "objectives",
        "plans",
        "replay",
        "search",
        "verifier",
    )
)
_ALL_INTERNAL_OWNERS = _OWNER_OWNERS | _FAMILY_OWNERS
_CANDIDATES = f"{_OPTIMIZATION_PACKAGE}.candidates"
_BUDGETS = f"{_OPTIMIZATION_PACKAGE}.budgets"
_REPLAY = f"{_OPTIMIZATION_PACKAGE}.replay"
_SEARCH = f"{_OPTIMIZATION_PACKAGE}.search"


def _dag_violations(source: str, package: str, owner: str) -> set[str]:
    """Enforce durable layer boundaries without freezing every optional edge."""
    edges = _owner_import_edges(source, package)
    violations: set[str] = set()
    constrained: frozenset[str] | None = None
    if owner in {"package", "families_barrel", "budgets"}:
        constrained = frozenset()
    elif owner == "candidates":
        constrained = frozenset({_BUDGETS})
    elif owner in _FAMILY_NAMES or owner == "replay":
        constrained = frozenset({_BUDGETS, _CANDIDATES})

    for edge in edges:
        if edge == _OPTIMIZATION_PACKAGE:
            violations.add(f"barrel:{edge}")
        elif edge == "py_science.formula.service" or edge.startswith("py_science.formula.service."):
            violations.add(f"service:{edge}")
        elif edge == "py_science.formula.optimization" or edge.startswith(
            "py_science.formula.optimization."
        ):
            violations.add(f"facade:{edge}")
        elif edge in _ALL_INTERNAL_OWNERS:
            wrong_layer = constrained is not None and edge not in constrained
            verifier_reverse_edge = owner == "verifier" and (
                edge == _SEARCH or edge in _FAMILY_OWNERS
            )
            lower_owner_search_edge = (
                owner in {"canonical", "objectives", "plans"} and edge == _SEARCH
            )
            if wrong_layer or verifier_reverse_edge or lower_owner_search_edge:
                violations.add(f"{owner}->{edge}")
    return violations


def _cycle(graph: dict[str, set[str]]) -> tuple[str, ...] | None:
    """Return one internal dependency cycle, when present."""
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(owner: str) -> tuple[str, ...] | None:
        if owner in visiting:
            start = visiting.index(owner)
            return (*visiting[start:], owner)
        if owner in visited:
            return None
        visiting.append(owner)
        for dependency in sorted(graph.get(owner, set())):
            found = visit(dependency)
            if found is not None:
                return found
        visiting.pop()
        visited.add(owner)
        return None

    for owner in sorted(graph):
        found = visit(owner)
        if found is not None:
            return found
    return None


_SERVICE_PACKAGE = "py_science.formula._service"
_SERVICE_NAMES = frozenset(
    {"optimization", "orchestration", "query_execution", "result_bounds", "scenario_execution"}
)
_SERVICE_OWNERS = frozenset(f"{_SERVICE_PACKAGE}.{name}" for name in _SERVICE_NAMES)


def _service_dag_violations(source: str) -> set[str]:
    edges = _owner_import_edges(source, _SERVICE_PACKAGE)
    violations: set[str] = set()
    for edge in edges:
        if edge == _SERVICE_PACKAGE:
            violations.add(f"barrel:{edge}")
        elif edge == "py_science.formula.service" or edge.startswith("py_science.formula.service."):
            violations.add(f"facade:{edge}")
        elif edge == "py_science.formula.optimization" or edge.startswith(
            "py_science.formula.optimization."
        ):
            violations.add(f"optimizer-facade:{edge}")
    return violations


def test_service_owner_dag_uses_direct_acyclic_seams_and_falsified_regressions() -> None:
    from py_science.formula._service import orchestration

    root = Path(orchestration.__file__).parent
    paths = {name: root / f"{name}.py" for name in _SERVICE_NAMES}
    sources = {name: path.read_text() for name, path in paths.items()}
    assert all(_service_dag_violations(source) == set() for source in sources.values())

    graph = {
        f"{_SERVICE_PACKAGE}.{name}": _owner_import_edges(source, _SERVICE_PACKAGE)
        & _SERVICE_OWNERS
        for name, source in sources.items()
    }
    assert _cycle(graph) is None
    assert {
        f"{_SERVICE_PACKAGE}.query_execution",
        f"{_SERVICE_PACKAGE}.result_bounds",
        f"{_SERVICE_PACKAGE}.scenario_execution",
    } <= graph[f"{_SERVICE_PACKAGE}.orchestration"]
    assert f"{_SERVICE_PACKAGE}.optimization" not in graph[f"{_SERVICE_PACKAGE}.orchestration"]
    assert f"{_SERVICE_PACKAGE}.result_bounds" in graph[f"{_SERVICE_PACKAGE}.optimization"]
    assert _service_dag_violations("from py_science.formula.service import analyze\n") == {
        "facade:py_science.formula.service",
        "facade:py_science.formula.service.analyze",
    }
    assert _service_dag_violations(
        "from py_science.formula.optimization import _optimization_result\n"
    ) == {
        "optimizer-facade:py_science.formula.optimization",
        "optimizer-facade:py_science.formula.optimization._optimization_result",
    }
    assert _service_dag_violations("from . import orchestration\n") == {
        f"barrel:{_SERVICE_PACKAGE}"
    }
    assert _cycle({"a": {"b"}, "b": {"a"}}) == ("a", "b", "a")


def test_owner_dag_covers_all_families_and_falsifies_every_rule() -> None:
    """The source census enforces required seams, layer direction, and acyclicity."""
    from py_science.formula._optimization import search

    root = Path(search.__file__).parent
    owners = {
        name: root / f"{name}.py"
        for name in (
            "budgets",
            "candidates",
            "canonical",
            "objectives",
            "plans",
            "replay",
            "search",
            "verifier",
        )
    }
    families = {
        path.stem: path for path in (root / "families").glob("*.py") if path.stem != "__init__"
    }
    assert set(families) == _FAMILY_NAMES
    scanned = {
        "package": (root / "__init__.py", _OPTIMIZATION_PACKAGE),
        "families_barrel": (root / "families" / "__init__.py", _FAMILY_PACKAGE),
        **{name: (path, _OPTIMIZATION_PACKAGE) for name, path in owners.items()},
        **{name: (path, _FAMILY_PACKAGE) for name, path in families.items()},
    }
    for name, (path, package) in scanned.items():
        assert _dag_violations(path.read_text(), package, name) == set(), name

    sources = {
        name: _owner_import_edges(path.read_text(), package) & _ALL_INTERNAL_OWNERS
        for name, (path, package) in scanned.items()
        if name not in {"package", "families_barrel"}
    }
    qualified_sources = {
        (
            f"{_FAMILY_PACKAGE}.{name}"
            if name in _FAMILY_NAMES
            else f"{_OPTIMIZATION_PACKAGE}.{name}"
        ): dependencies
        for name, dependencies in sources.items()
    }
    assert _cycle(qualified_sources) is None

    required = {
        _REPLAY: {_CANDIDATES},
        f"{_OPTIMIZATION_PACKAGE}.verifier": {_REPLAY},
        _SEARCH: {
            _BUDGETS,
            _CANDIDATES,
            f"{_OPTIMIZATION_PACKAGE}.canonical",
            f"{_OPTIMIZATION_PACKAGE}.objectives",
            f"{_OPTIMIZATION_PACKAGE}.plans",
            f"{_OPTIMIZATION_PACKAGE}.verifier",
            *_FAMILY_OWNERS,
        },
    }
    for owner, dependencies in required.items():
        assert dependencies <= qualified_sources[owner]
    for family in _FAMILY_OWNERS:
        assert _CANDIDATES in qualified_sources[family]

    # Absolute, relative, and barrel spellings each falsify an enforced rule.
    assert _dag_violations("from . import verifier\n", _OPTIMIZATION_PACKAGE, "search") == {
        f"barrel:{_OPTIMIZATION_PACKAGE}"
    }
    assert _dag_violations("from .. import candidates\n", _FAMILY_PACKAGE, "factoring") == {
        f"barrel:{_OPTIMIZATION_PACKAGE}"
    }
    assert _dag_violations(
        "from py_science.formula._optimization import verifier\n", _OPTIMIZATION_PACKAGE, "search"
    ) == {f"barrel:{_OPTIMIZATION_PACKAGE}"}
    assert _dag_violations(
        "from py_science.formula import optimization\n", _OPTIMIZATION_PACKAGE, "search"
    ) == {"facade:py_science.formula.optimization"}
    assert _dag_violations(f"import {_REPLAY}\n", _FAMILY_PACKAGE, "factoring") == {
        f"factoring->{_REPLAY}"
    }
    assert _dag_violations(
        f"import {_OPTIMIZATION_PACKAGE}.verifier\n", _OPTIMIZATION_PACKAGE, "replay"
    ) == {f"replay->{_OPTIMIZATION_PACKAGE}.verifier"}
    assert _dag_violations(f"import {_SEARCH}\n", _OPTIMIZATION_PACKAGE, "verifier") == {
        f"verifier->{_SEARCH}"
    }
    assert _dag_violations(f"import {_CANDIDATES}\n", _FAMILY_PACKAGE, "factoring") == set()
    assert _cycle({"a": {"b"}, "b": {"a"}}) == ("a", "b", "a")


def test_facade_private_consumers_are_direct_owner_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The compatibility facade preserves objects, while mutable seams live with owners."""
    import inspect

    import py_science.formula.optimization as facade
    from py_science.formula import AnalysisFailure, AnalysisRequest, FormulaSyntax
    from py_science.formula._analysis import occurrences
    from py_science.formula._analysis.computation import analyze_retained
    from py_science.formula._optimization import (
        budgets,
        candidates,
        canonical,
        objectives,
        replay,
        search,
        verifier,
    )
    from py_science.formula._optimization.families import (
        cross_equation_sharing,
        factoring,
        horner,
        redundant_operations,
    )
    from py_science.formula.reasoning import ReasoningContext

    owner_aliases = {
        "_optimization_result": search._optimization_result,
        "_CandidateComputation": candidates._CandidateComputation,
        "_CandidateDescriptor": candidates._CandidateDescriptor,
        "_Accepted": verifier._Accepted,
        "_OptimizationBudget": budgets._OptimizationBudget,
        "_OptimizationBudgetConfig": budgets._OptimizationBudgetConfig,
        "_RetainedLaneCollector": search._RetainedLaneCollector,
        "_generate_candidate_lanes": search._generate_candidate_lanes,
        "_generate_candidates": search._generate_candidates,
        "_complete_candidate": replay._complete_candidate,
        "_complete_candidate_schedule": search._complete_candidate_schedule,
        "_candidate_semantic_key": canonical._candidate_semantic_key,
        "_adjacent_ordering_relation": objectives._adjacent_ordering_relation,
        "_qualifications_compatible": verifier._qualifications_compatible,
        "_EvaluationScope": occurrences._EvaluationScope,
        "_Occurrence": occurrences._Occurrence,
        "_FAMILY_ORDER": search._FAMILY_ORDER,
        "_verify_candidate": verifier._verify_candidate,
        "ReasoningContext": ReasoningContext,
        "_default_budget_config": budgets._default_budget_config,
        "_accepted_order": objectives._accepted_order,
        "_cross_equation_descriptors": cross_equation_sharing._cross_equation_descriptors,
        "_factor_term": factoring._factor_term,
        "_factored": factoring._factored,
        "_horner_candidate": horner._horner_candidate,
        "_neutral_replacement": redundant_operations._neutral_replacement,
        "substitute": cross_equation_sharing.substitute,
    }
    for name, owner in owner_aliases.items():
        assert getattr(facade, name) is owner, name
    for name in vars(budgets):
        if name.startswith("MAX_"):
            assert getattr(facade, name) is getattr(budgets, name), name
    assert inspect.signature(facade._optimization_result) == inspect.signature(
        search._optimization_result
    )

    request = AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 0")
    computed = analyze_retained(request)
    assert not isinstance(computed, AnalysisFailure)
    monkeypatch.setattr(budgets, "MAX_OPTIMIZATION_CANDIDATES", 0)
    _candidates, qualifications = facade._generate_candidates(
        computed, facade._OptimizationBudget(facade._default_budget_config())
    )
    assert "generated transitions budget exhausted" in qualifications[0]
    monkeypatch.undo()
    assert budgets.MAX_OPTIMIZATION_CANDIDATES == facade.MAX_OPTIMIZATION_CANDIDATES
    candidates_after_restore, qualifications_after_restore = facade._generate_candidates(
        computed, facade._OptimizationBudget()
    )
    assert candidates_after_restore and not qualifications_after_restore
