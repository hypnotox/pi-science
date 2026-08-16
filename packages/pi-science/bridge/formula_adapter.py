#!/usr/bin/env python3
"""Private JSON-lines adapter; stdout is reserved for exactly one response."""
import json
import sys
from pydantic import ValidationError
from py_science.formula import AnalysisRequest, analyze

PROTOCOL_VERSION = 1

def response(payload):
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))

def main():
    if sys.argv[1:] == ["--health"]:
        response({"version": PROTOCOL_VERSION, "result": {"status": "healthy"}})
        return 0
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict) or request.get("version") != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        result = analyze(AnalysisRequest.model_validate(request.get("request")))
        response({"version": PROTOCOL_VERSION, "result": result.model_dump(mode="json")})
    except (ValueError, TypeError, json.JSONDecodeError, ValidationError) as error:
        response({"version": PROTOCOL_VERSION, "error": {"kind": "request", "message": str(error)}})
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
