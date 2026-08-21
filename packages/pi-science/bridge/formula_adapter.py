#!/usr/bin/env python3
"""Private bounded JSON adapter; stdout is reserved for exactly one response."""

from __future__ import annotations

import json
import sys
from typing import Any, cast

from py_science.formula import (
    AnalysisRequest,
    CandidateComparisonRequest,
    DominanceAnalysisRequest,
    OptimizeRequest,
    analyze,
    analyze_dominance,
    compare_candidates,
    optimize,
)
from pydantic import TypeAdapter, ValidationError

PROTOCOL_VERSION = 13
REQUEST_ADAPTER: TypeAdapter[
    AnalysisRequest | CandidateComparisonRequest | DominanceAnalysisRequest | OptimizeRequest
] = TypeAdapter(
    AnalysisRequest | CandidateComparisonRequest | DominanceAnalysisRequest | OptimizeRequest
)
# The public request permits 262,144 UTF-8 source bytes. This whole-envelope
# limit also covers JSON escaping and every bounded collection/name field.
MAX_ENVELOPE_BYTES = 2_097_152
# Python preserves 262,144 base-result bytes and separately allows 65,536
# optimization bytes; this ceiling adds 256 bytes of bounded protocol framing.
MAX_RESPONSE_BYTES = 524_544
MAX_DIAGNOSTIC_BYTES = 4_096


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _encoded(payload: dict[str, Any]) -> bytes | None:
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    chunks: list[bytes] = []
    size = 0
    for chunk in encoder.iterencode(payload):
        encoded = chunk.encode("utf-8")
        size += len(encoded)
        if size + 1 > MAX_RESPONSE_BYTES:
            return None
        chunks.append(encoded)
    chunks.append(b"\n")
    return b"".join(chunks)


def response(payload: dict[str, Any]) -> bool:
    encoded = _encoded(payload)
    if encoded is None:
        return False
    sys.stdout.buffer.write(encoded)
    return True


def _request_error(error: Exception) -> int:
    message = str(error).encode("utf-8")[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", "ignore")
    response(
        {
            "version": PROTOCOL_VERSION,
            "error": {"kind": "request", "message": message},
        }
    )
    return 2


def main() -> int:
    if sys.argv[1:] == ["--health"]:
        response({"version": PROTOCOL_VERSION, "result": {"status": "healthy"}})
        return 0
    try:
        raw = sys.stdin.buffer.read(MAX_ENVELOPE_BYTES + 1)
        if len(raw) > MAX_ENVELOPE_BYTES:
            raise ValueError("protocol envelope exceeds its 2,097,152-byte UTF-8 bound")
        envelope = json.loads(raw, object_pairs_hook=_strict_object)
        if not isinstance(envelope, dict):
            raise ValueError("invalid protocol envelope")
        typed_envelope = cast(dict[str, object], envelope)
        if len(typed_envelope) != 2 or set(typed_envelope) != {"version", "request"}:
            raise ValueError("invalid protocol envelope")
        if typed_envelope["version"] != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        request_payload = typed_envelope["request"]
        if not isinstance(request_payload, dict):
            raise ValueError("invalid analysis request")
        # JSON validation preserves the strict frozen public contract while accepting
        # JSON arrays for tuple fields. Mathematical policy remains in Python.
        request = REQUEST_ADAPTER.validate_json(
            json.dumps(request_payload, ensure_ascii=False, separators=(",", ":"))
        )
        if getattr(request, "operation", None) == "optimize":
            outcome = optimize(cast(OptimizeRequest, request))
            result = outcome.model_dump(mode="json", exclude_none=False)
        elif getattr(request, "operation", None) == "compare_candidates":
            outcome = compare_candidates(cast(CandidateComparisonRequest, request))
            result = outcome.model_dump(mode="json", exclude_none=False)
        elif getattr(request, "operation", None) == "analyze_dominance":
            outcome = analyze_dominance(cast(DominanceAnalysisRequest, request))
            result = outcome.model_dump(mode="json", exclude_none=False)
        else:
            outcome = analyze(cast(AnalysisRequest, request))
            result = outcome.model_dump(mode="json", exclude_none=True)
            if outcome.status == "success":
                result["abstract_work"] = outcome.abstract_work
                result["queries"] = [query.model_dump(mode="json") for query in outcome.queries]
                assert outcome.optimization is not None
                # Optimization target/intermediate nulls are correlation-bearing
                # protocol fields, unlike absent optional ordinary report sections.
                result["optimization"] = outcome.optimization.model_dump(
                    mode="json", exclude_none=False
                )
                if outcome.system is not None:
                    system_result = result["system"]
                    counts = outcome.system.aggregate_operation_counts
                    system_result.update(
                        {
                            "aggregate_operation_counts": counts.model_dump(mode="json")
                            if counts is not None
                            else None,
                            "total_work": outcome.system.total_work,
                            "primitive_invocations": outcome.system.primitive_invocations,
                        }
                    )
                    for equation_result, equation in zip(
                        system_result["equations"], outcome.system.equations, strict=True
                    ):
                        counts = equation.aggregate_operation_counts
                        equation_result.update(
                            {
                                "aggregate_operation_counts": counts.model_dump(mode="json")
                                if counts is not None
                                else None,
                                "aggregate_work": equation.aggregate_work,
                                "primitive_invocations": equation.primitive_invocations,
                            }
                        )
        if outcome.status == "failure":
            error = result["error"]
            error.update(
                {
                    "location": outcome.error.location.model_dump(mode="json")
                    if outcome.error.location
                    else None,
                    "source": outcome.error.source.model_dump(mode="json")
                    if outcome.error.source
                    else None,
                    "supported_alternative": outcome.error.supported_alternative,
                }
            )
        if not response({"version": PROTOCOL_VERSION, "result": result}):
            response(
                {
                    "version": PROTOCOL_VERSION,
                    "error": {
                        "kind": "internal",
                        "message": "formula adapter response exceeds its bound",
                    },
                }
            )
            return 3
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        ValidationError,
    ) as error:
        return _request_error(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
