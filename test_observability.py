# tests/test_observability.py
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import requests

BASE_URL = "http://127.0.0.1:5001"
GRAPHQL_URL = f"{BASE_URL}/graphql"
LOG_PATH = Path("logs/graphql_test.log")


def gql(query: str, variables: Optional[Dict[str, Any]] = None, operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None) -> requests.Response:
    payload: Dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    if operation_name is not None:
        payload["operationName"] = operation_name

    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)

    return requests.post(GRAPHQL_URL, json=payload, headers=h, timeout=15)


def read_json_log_lines() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            # ignore non-json lines
            continue
    return out


def wait_for_log_event(event: str, request_id: Optional[str] = None, timeout_s: float = 3.0) -> dict:
    """
    Poll the log file until a matching event appears.
    """
    start = time.time()
    while time.time() - start < timeout_s:
        entries = read_json_log_lines()
        for e in reversed(entries):
            if e.get("event") != event:
                continue
            if request_id and e.get("request_id") != request_id:
                continue
            return e
        time.sleep(0.1)
    raise AssertionError(f"Did not find log event={event} request_id={request_id}. "
                         f"Last entries: {read_json_log_lines()[-5:]}")


@pytest.fixture(autouse=True)
def ensure_log_dir():
    os.makedirs("logs", exist_ok=True)


@pytest.mark.observability
def test_graphql_logs_request_id_and_duration_success():
    q = 'query IntrospectMe { __type(name: "Query") { fields { name } } }'
    r = gql(q, operation_name="IntrospectMe")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body

    rid = r.headers.get("X-Request-Id")
    assert rid, "Expected X-Request-Id header from server"

    log = wait_for_log_event("graphql_request", request_id=rid)
    assert log["request_id"] == rid
    assert log["operation_name"] == "IntrospectMe"
    assert log["operation_type"] in ("query", "mutation", "unknown")
    assert isinstance(log["duration_ms"], int)
    assert log["duration_ms"] >= 0


@pytest.mark.observability
def test_graphql_respects_incoming_x_request_id():
    incoming = "test-request-id-12345"
    q = 'query MyOp { __type(name: "Query") { name } }'
    r = gql(q, operation_name="MyOp", headers={"X-Request-Id": incoming})
    assert r.status_code == 200

    assert r.headers.get("X-Request-Id") == incoming
    log = wait_for_log_event("graphql_request", request_id=incoming)
    assert log["request_id"] == incoming
    assert log["operation_name"] == "MyOp"


@pytest.mark.observability
def test_graphql_logs_operation_type_mutation():
    mutation = """
    mutation CreatePetOp($name: String!, $type: String!, $status: String) {
      createPet(name: $name, type: $type, status: $status) { id name type status }
    }
    """
    vars_ = {"name": "Obs Dog", "type": "dog", "status": "available"}
    r = gql(mutation, variables=vars_, operation_name="CreatePetOp")
    assert r.status_code == 200
    data = r.json()
    assert "errors" not in data

    rid = r.headers.get("X-Request-Id")
    assert rid

    log = wait_for_log_event("graphql_request", request_id=rid)
    assert log["operation_name"] == "CreatePetOp"
    assert log["operation_type"] == "mutation"


@pytest.mark.observability
def test_graphql_logs_structured_errors():
    bad_query = "query BadOne { definitelyNotARealField }"
    r = gql(bad_query, operation_name="BadOne")
    assert r.status_code in (200, 400)
    body = r.json()
    assert "errors" in body and body["errors"]

    rid = r.headers.get("X-Request-Id")
    assert rid

    log = wait_for_log_event("graphql_error", request_id=rid)
    assert log["operation_name"] == "BadOne"
    assert isinstance(log.get("errors"), list) and len(log["errors"]) >= 1
    assert any(isinstance(m, str) and m for m in log["errors"])


@pytest.mark.observability
def test_graphql_duration_is_reasonable():
    q = 'query QuickCheck { __type(name: "Query") { name } }'
    r = gql(q, operation_name="QuickCheck")
    assert r.status_code == 200

    rid = r.headers.get("X-Request-Id")
    assert rid

    log = wait_for_log_event("graphql_request", request_id=rid)
    assert isinstance(log["duration_ms"], int)
    assert 0 <= log["duration_ms"] < 5000


"""
Observability & Logging Validation Tests

These tests validate structured logging and request tracing behavior
for the GraphQL middleware layer.

Why this matters:
- STRATA acts as an API/data highway and must provide strong request traceability.
- Middleware systems require correlation IDs to debug cross-domain issues.
- These tests ensure:
    • Every request generates or propagates a request_id
    • request_id is returned in the response headers
    • Structured JSON logs are written for each request
    • Errors are logged with metadata (operation_name, type, duration)
    • Execution time (duration_ms) is captured for performance insight

This simulates enterprise-grade observability expectations in financial systems.
"""
