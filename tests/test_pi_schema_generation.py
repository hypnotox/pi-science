from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
GENERATOR = ROOT / "scripts" / "generate-pi-formula-schema.py"
ARTIFACT = ROOT / "packages" / "pi-science" / "src" / "formula-schema.json"
FORBIDDEN_KEYS = {"$defs", "$ref", "const", "discriminator", "oneOf", "title"}


def _generate(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _walk(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return [mapping, *(item for child in mapping.values() for item in _walk(child))]
    if isinstance(value, list):
        sequence = cast(list[object], value)
        return [item for child in sequence for item in _walk(child)]
    return []


def test_generated_pi_schema_is_deterministic_and_current(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    first_result = _generate(first)
    second_result = _generate(second)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert first.read_bytes() == second.read_bytes() == ARTIFACT.read_bytes()
    check = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr


def test_generated_pi_schema_uses_the_pinned_provider_safe_subset() -> None:
    schema = json.loads(ARTIFACT.read_text())
    nodes = _walk(schema)

    assert not ({key for node in nodes for key in node} & FORBIDDEN_KEYS)
    assert all(
        not ("enum" in node and node.get("type") == "string")
        or all(isinstance(choice, str) for choice in node["enum"])
        for node in nodes
    )
    assert all(
        not (
            "anyOf" in node
            and all(isinstance(option, dict) and "enum" in option for option in node["anyOf"])
        )
        for node in nodes
    )


def test_generated_pi_schema_has_public_expression_and_system_branches() -> None:
    schema = json.loads(ARTIFACT.read_text())

    expression, system = schema["anyOf"]
    assert expression["required"] == ["expression"]
    assert "syntax" not in expression["properties"]
    assert "equations" not in expression["properties"]
    assert expression["properties"]["expression"] == {
        "maxLength": 65_536,
        "minLength": 1,
        "type": "string",
    }
    assert system["required"] == ["equations"]
    assert "syntax" not in system["properties"]
    assert "expression" not in system["properties"]
    assert system["properties"]["equations"]["minItems"] == 1
    assert system["properties"]["equations"]["maxItems"] == 128


def test_generated_pi_schema_preserves_query_and_population_bounds() -> None:
    schema = json.loads(ARTIFACT.read_text())
    expression, system = schema["anyOf"]

    assert expression["properties"]["queries"]["maxItems"] == 32
    assert system["properties"]["queries"]["maxItems"] == 32
    assert expression["properties"]["scenarios"]["maxItems"] == 64
    assert system["properties"]["equations"]["items"]["properties"]["name"]["maxLength"] == 128

    expression_queries = expression["properties"]["queries"]["items"]["anyOf"]
    system_queries = system["properties"]["queries"]["items"]["anyOf"]
    assert {variant["properties"]["kind"]["enum"][0] for variant in expression_queries} == {
        "equivalence",
        "closed_form",
        "properties",
        "limit",
        "asymptotic",
    }
    assert all("target" not in variant["properties"] for variant in expression_queries)
    assert all("target" in variant["required"] for variant in system_queries)
