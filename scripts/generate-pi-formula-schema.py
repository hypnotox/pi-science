#!/usr/bin/env python3
"""Generate the provider-facing Pi schema from the Python request model."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from py_science.formula import (
    AnalysisRequest,
    CandidateComparisonRequest,
    DominanceAnalysisRequest,
    OptimizeRequest,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "packages" / "pi-science" / "src" / "formula-schema.json"
ALLOWED_SCHEMA_KEYS = {
    "additionalProperties",
    "anyOf",
    "description",
    "default",
    "enum",
    "items",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "pattern",
    "properties",
    "required",
    "type",
    "uniqueItems",
}

JsonObject = dict[str, Any]


def _resolve_reference(reference: str, definitions: dict[str, JsonObject]) -> JsonObject:
    prefix = "#/$defs/"
    if not reference.startswith(prefix):
        raise ValueError(f"unsupported schema reference: {reference}")
    name = reference.removeprefix(prefix)
    if name not in definitions:
        raise ValueError(f"unknown schema reference: {reference}")
    return copy.deepcopy(definitions[name])


def _normalize(value: Any, definitions: dict[str, JsonObject]) -> Any:
    if isinstance(value, list):
        return [_normalize(item, definitions) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        if set(value) != {"$ref"}:
            raise ValueError("schema references with sibling keywords are unsupported")
        return _normalize(_resolve_reference(value["$ref"], definitions), definitions)

    source = {key: item for key, item in value.items() if key not in {"default", "title"}}
    source.pop("discriminator", None)
    if "const" in source:
        source["enum"] = [source.pop("const")]
    if "oneOf" in source:
        if "anyOf" in source:
            raise ValueError("schema node contains both oneOf and anyOf")
        source["anyOf"] = source.pop("oneOf")

    normalized = {key: _normalize(item, definitions) for key, item in source.items()}
    if "anyOf" in normalized:
        options = [option for option in normalized["anyOf"] if option != {"type": "null"}]
        if len(options) == 1 and set(normalized) == {"anyOf"}:
            return options[0]
        normalized["anyOf"] = options
    if normalized.get("type") == "object" and isinstance(source.get("properties"), dict):
        required = list(normalized.get("required", []))
        for name, property_schema in source["properties"].items():
            if (
                isinstance(property_schema, dict)
                and "const" in property_schema
                and name not in required
            ):
                required.append(name)
        if required:
            normalized["required"] = required
    return normalized


def _query_references(query_schema: JsonObject) -> list[str]:
    items = query_schema.get("items")
    if not isinstance(items, dict) or not isinstance(items.get("oneOf"), list):
        raise ValueError("AnalysisRequest query union is not a discriminated oneOf")
    references: list[str] = []
    for option in items["oneOf"]:
        if not isinstance(option, dict) or set(option) != {"$ref"}:
            raise ValueError("AnalysisRequest query union contains a non-reference variant")
        references.append(option["$ref"])
    if not references:
        raise ValueError("AnalysisRequest query union is empty")
    return references


def _query_variants(
    definitions: dict[str, JsonObject], query_schema: JsonObject, *, system: bool
) -> list[JsonObject]:
    variants: list[JsonObject] = []
    for reference in _query_references(query_schema):
        variant = _normalize(_resolve_reference(reference, definitions), definitions)
        properties = variant["properties"]
        required = list(variant.get("required", []))
        target = properties.get("target")
        kind = properties["kind"]["enum"][0]
        if system:
            if target is not None and "target" not in required:
                required.append("target")
            # Closed form remains equation-only; every downstream analysis
            # query may explicitly consume an earlier verified candidate.
            if target is not None and kind not in {
                "equivalence",
                "properties",
                "limit",
                "asymptotic",
            }:
                options = target.get("anyOf") if isinstance(target, dict) else None
                if isinstance(options, list):
                    equation = [
                        item
                        for item in options
                        if item.get("properties", {}).get("kind", {}).get("enum") == ["equation"]
                    ]
                    properties["target"] = {"anyOf": equation}
        elif target is not None:
            if kind not in {"equivalence", "properties", "limit", "asymptotic"}:
                properties.pop("target")
                variant["required"] = [field for field in required if field != "target"]
                variants.append(variant)
                continue
            # Expression requests may select only a derived operand; equation
            # targets remain a system-only spelling.
            options = target.get("anyOf", []) if isinstance(target, dict) else []
            derived = [
                item
                for item in options
                if item.get("properties", {}).get("kind", {}).get("enum") == ["derived"]
            ]
            if derived:
                properties["target"] = {"anyOf": derived}
            else:
                properties.pop("target")
            required = [field for field in required if field != "target"]
        variant["required"] = required
        variants.append(variant)
    return variants


def validate_schema(schema: JsonObject, path: str = "$") -> None:
    unsupported = set(schema) - ALLOWED_SCHEMA_KEYS
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"unsupported Pi schema keyword(s) at {path}: {names}")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"Pi schema properties must be an object at {path}")
    for name, child in properties.items():
        if not isinstance(child, dict):
            raise ValueError(f"Pi schema property must be an object at {path}.{name}")
        validate_schema(child, f"{path}.properties.{name}")
    items = schema.get("items")
    if items is not None:
        if not isinstance(items, dict):
            raise ValueError(f"Pi schema items must be an object at {path}")
        validate_schema(items, f"{path}.items")
    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        validate_schema(additional, f"{path}.additionalProperties")
    alternatives = schema.get("anyOf", [])
    if not isinstance(alternatives, list):
        raise ValueError(f"Pi schema anyOf must be an array at {path}")
    for index, child in enumerate(alternatives):
        if not isinstance(child, dict):
            raise ValueError(f"Pi schema anyOf member must be an object at {path}[{index}]")
        validate_schema(child, f"{path}.anyOf[{index}]")


def generate_schema() -> JsonObject:
    raw = AnalysisRequest.model_json_schema()
    definitions = raw.get("$defs")
    properties = raw.get("properties")
    if not isinstance(definitions, dict) or not isinstance(properties, dict):
        raise ValueError("AnalysisRequest emitted an incompatible JSON Schema")

    metadata = {
        name: _normalize(copy.deepcopy(schema), definitions)
        for name, schema in properties.items()
        if name not in {"syntax", "expression", "equations", "queries"}
    }
    outputs = metadata.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("AnalysisRequest output identities schema is unavailable")
    outputs["uniqueItems"] = True
    query_schema = properties["queries"]
    expression_queries = {
        "items": {"anyOf": _query_variants(definitions, query_schema, system=False)},
        "maxItems": query_schema["maxItems"],
        "type": "array",
    }
    system_queries = {
        "items": {"anyOf": _query_variants(definitions, query_schema, system=True)},
        "maxItems": query_schema["maxItems"],
        "type": "array",
    }
    expression = {
        "additionalProperties": False,
        "properties": {
            "expression": _normalize(copy.deepcopy(properties["expression"]), definitions),
            **copy.deepcopy(metadata),
            "queries": expression_queries,
        },
        "required": ["expression"],
        "type": "object",
    }
    equations = _normalize(copy.deepcopy(properties["equations"]), definitions)
    equations["minItems"] = 1
    system = {
        "additionalProperties": False,
        "properties": {
            "equations": equations,
            **copy.deepcopy(metadata),
            "queries": system_queries,
        },
        "required": ["equations"],
        "type": "object",
    }
    comparison_raw = CandidateComparisonRequest.model_json_schema()
    comparison_definitions = comparison_raw.get("$defs")
    comparison_properties = comparison_raw.get("properties")
    if not isinstance(comparison_definitions, dict) or not isinstance(comparison_properties, dict):
        raise ValueError("CandidateComparisonRequest emitted an incompatible JSON Schema")
    comparison = _normalize(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": comparison_properties,
            "required": comparison_raw.get("required", []),
        },
        comparison_definitions,
    )
    # Pi supplies the fixed backend syntax; callers cannot select it.
    comparison["properties"].pop("syntax", None)
    comparison["required"] = [name for name in comparison["required"] if name != "syntax"]
    candidate = comparison["properties"]["candidates"]["items"]
    candidate_properties = candidate["properties"]
    candidate_name = copy.deepcopy(candidate_properties["name"])
    candidate_expression = {
        "additionalProperties": False,
        "properties": {
            "name": copy.deepcopy(candidate_name),
            "expression": copy.deepcopy(candidate_properties["expression"]),
        },
        "required": ["name", "expression"],
        "type": "object",
    }
    candidate_equations = copy.deepcopy(candidate_properties["equations"])
    candidate_equations["minItems"] = 1
    candidate_system = {
        "additionalProperties": False,
        "properties": {
            "name": candidate_name,
            "equations": candidate_equations,
        },
        "required": ["name", "equations"],
        "type": "object",
    }
    comparison["properties"]["candidates"]["items"] = {
        "anyOf": [candidate_expression, candidate_system]
    }
    dominance_raw = DominanceAnalysisRequest.model_json_schema()
    dominance_definitions = dominance_raw.get("$defs")
    dominance_properties = dominance_raw.get("properties")
    if not isinstance(dominance_definitions, dict) or not isinstance(dominance_properties, dict):
        raise ValueError("DominanceAnalysisRequest emitted an incompatible JSON Schema")
    dominance_metadata = {
        name: _normalize(copy.deepcopy(item), dominance_definitions)
        for name, item in dominance_properties.items()
        if name not in {"syntax", "expression", "equations"}
    }
    dominance_expression = {
        "additionalProperties": False,
        "properties": {
            "expression": _normalize(
                copy.deepcopy(dominance_properties["expression"]), dominance_definitions
            ),
            **dominance_metadata,
        },
        "required": ["operation", "expression", "axis"],
        "type": "object",
    }
    dominance_equations = _normalize(
        copy.deepcopy(dominance_properties["equations"]), dominance_definitions
    )
    dominance_equations["minItems"] = 1
    dominance_system = {
        "additionalProperties": False,
        "properties": {"equations": dominance_equations, **dominance_metadata},
        "required": ["operation", "equations", "axis"],
        "type": "object",
    }
    optimize_raw = OptimizeRequest.model_json_schema()
    optimize_definitions = optimize_raw.get("$defs")
    optimize_properties = optimize_raw.get("properties")
    if not isinstance(optimize_definitions, dict) or not isinstance(optimize_properties, dict):
        raise ValueError("OptimizeRequest emitted an incompatible JSON Schema")
    optimize_metadata = {
        name: _normalize(copy.deepcopy(item), optimize_definitions)
        for name, item in optimize_properties.items()
        if name not in {"syntax", "expression", "equations"}
    }
    optimize_required = [
        name
        for name in optimize_raw.get("required", [])
        if name not in {"syntax", "expression", "equations"}
    ]
    optimize_expression = {
        "additionalProperties": False,
        "properties": {
            "expression": _normalize(
                copy.deepcopy(optimize_properties["expression"]), optimize_definitions
            ),
            **optimize_metadata,
        },
        "required": [*optimize_required, "expression"],
        "type": "object",
    }
    optimize_equations = _normalize(
        copy.deepcopy(optimize_properties["equations"]), optimize_definitions
    )
    optimize_equations["minItems"] = 1
    optimize_system = {
        "additionalProperties": False,
        "properties": {"equations": optimize_equations, **optimize_metadata},
        "required": [*optimize_required, "equations"],
        "type": "object",
    }
    schema = {
        "anyOf": [
            expression, system, comparison, dominance_expression, dominance_system,
            optimize_expression, optimize_system,
        ]
    }
    validate_schema(schema)
    return schema


def _encoded_schema() -> bytes:
    return (json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _encoded_schema()
    output = args.output.resolve()

    if args.check:
        try:
            actual = output.read_bytes()
        except FileNotFoundError:
            actual = b""
        if actual != expected:
            relative = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
            command = (
                f"uv run --locked python scripts/generate-pi-formula-schema.py --output {relative}"
            )
            print(
                f"generated Pi formula schema is stale: run `{command}`",
                file=sys.stderr,
            )
            return 1
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
