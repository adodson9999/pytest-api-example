"""
Observability & Logging Validation Tests

This module validates structured logging, request tracing, and observability
features in the GraphQL middleware layer.

Why This Matters for STRATA:
STRATA acts as an "API/data highway" handling 90% of communication at Ally.
Middleware platforms require enterprise-grade observability:
- Correlation IDs for distributed tracing
- Structured logging for log aggregation (Splunk, ELK, Datadog)
- Performance metrics (latency, error rates)
- Cross-service debugging capabilities
- Incident triage and root cause analysis

Key Concepts Demonstrated:
- Request ID propagation (X-Request-Id header)
- Automatic request ID generation when missing
- Structured JSON logging with metadata
- Operation-level tracking (query vs mutation)
- Duration measurement for performance monitoring
- Error logging with context preservation
- Correlation between requests and logs

Production Readiness:
These tests validate that the middleware upholds observability contracts
even under failure conditions. Without proper observability:
- Debugging production issues becomes impossible
- Performance regressions go unnoticed
- Cross-team collaboration suffers
- Incident resolution takes hours instead of minutes

This demonstrates "testing beyond functionality" - validating operational
requirements that separate hobby projects from enterprise systems.
"""

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
    """
    Execute a GraphQL request with optional headers for observability testing.
    
    How It Works:
    1. Builds GraphQL payload with query, variables, and operationName
    2. Merges custom headers (like X-Request-Id) with required Content-Type
    3. POSTs to GraphQL endpoint with 15-second timeout
    4. Returns full Response object (not just JSON) to access headers
    
    Why We Do This:
    Observability tests need to inspect BOTH response body AND headers:
    - Headers: X-Request-Id for correlation
    - Body: data/errors for functional validation
    
    Unlike functional tests (which only care about data), observability tests
    validate the "metadata layer" - correlation IDs, timing, and logging.
    
    The 15-second timeout is longer than functional tests (10s) because
    logging operations add overhead, especially when writing to disk.
    
    Design Decision: Returns Response object instead of parsed JSON to give
    tests full access to status codes, headers, and body.
    
    Args:
        query: GraphQL query or mutation string
        variables: Optional query variables dict
        operation_name: Optional operation name for multi-operation documents
        headers: Optional custom headers (e.g., X-Request-Id for propagation testing)
        
    Returns:
        requests.Response: Full HTTP response object with headers and body
        
    Q&A:
    
    Q1: Why return Response instead of just JSON like other test clients?
    A1: Observability tests MUST inspect headers (X-Request-Id). Returning
        Response gives access to both headers and body without multiple calls.
    
    Q2: Why 15-second timeout instead of 10?
    A2: File I/O for logging is slower than in-memory operations. Conservative
        timeout prevents false failures in slow CI environments.
    
    Q3: How does this differ from GraphQLClient class?
    A3: GraphQLClient is for functional tests (data validation). This is
        lightweight for observability tests (header/log validation).
    
    Q4: Why not use a shared client instance?
    A4: Observability tests need precise control over headers per request.
        Function approach is simpler than configuring client per test.
    
    Q5: What if the server doesn't return X-Request-Id?
    A5: Test fails! That's the point - tests validate observability contract
        is upheld. Missing correlation IDs break distributed tracing.
    
    Q6: How would you add authentication?
    A6: Add auth_token parameter:
        if auth_token: h["Authorization"] = f"Bearer {auth_token}"
    
    Q7: Why timeout at all?
    A7: Prevents tests from hanging indefinitely on server hangs or network
        issues. Better to fail fast than wait forever.
    
    Q8: Could this support retry logic?
    A8: Yes, but for observability tests, retries obscure timing measurements.
        Want to measure actual first-attempt performance.
    
    Q9: What about connection pooling?
    A9: requests.Session() provides pooling. For observability tests,
        isolated connections per test are cleaner (no shared state).
    
    Q10: How does STRATA handle correlation IDs differently?
    A10: Uses OpenTelemetry or similar for automatic propagation across
         services, not just HTTP headers. Integrates with APM tools.
    """
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
    """
    Read and parse JSON log lines from the log file.
    
    How It Works:
    1. Checks if log file exists (returns empty list if not)
    2. Reads entire file as text (UTF-8 encoding for internationalization)
    3. Splits into individual lines
    4. Attempts to parse each line as JSON
    5. Silently skips malformed lines (graceful degradation)
    6. Returns list of successfully parsed log entries
    
    Why We Do This:
    Structured logging means each log line is a JSON object.
    Tests need to parse logs to verify:
    - Correct events are logged (graphql_request, graphql_error)
    - Metadata is present (request_id, operation_name, duration_ms)
    - Correlation IDs match between request and logs
    
    This implements "log assertion" pattern - tests verify not just
    application behavior, but also observability artifacts.
    
    Critical for STRATA because:
    - Log aggregation systems depend on structured JSON
    - Malformed logs break log parsing pipelines
    - Missing metadata makes debugging impossible
    
    Design Decision: Silent failure on malformed lines allows partial
    validation even if some log entries are corrupted.
    
    Returns:
        list[dict]: List of parsed JSON log entries (may be empty)
        
    Q&A:
    
    Q1: Why return empty list instead of None if file doesn't exist?
    A1: Pythonic: allows for entry in read_json_log_lines() to work
        without None checks. Empty list is safer iteration target.
    
    Q2: Why silently skip malformed JSON instead of failing?
    A2: Log files may contain debug output, stack traces, or other
        non-JSON lines. Tests only care about structured entries.
    
    Q3: What if log file is huge (millions of lines)?
    A3: Performance issue. Solution: read last N lines only, or use
        log rotation + reading only current rotation file.
    
    Q4: Why read entire file instead of streaming?
    A4: Test log files are small (<1MB). For production monitoring,
        use streaming parsers or tail -f equivalent.
    
    Q5: How do you prevent test pollution (old logs)?
    A5: Clear log file in test setup (fixture), or use unique log
        files per test run (timestamped filenames).
    
    Q6: What encoding issues might occur?
    A6: Non-ASCII characters in error messages. UTF-8 handles this.
        Without encoding parameter, might get UnicodeDecodeError.
    
    Q7: Why list[dict] return type instead of List[Dict]?
    A7: Python 3.9+ supports lowercase type hints. More modern and
        cleaner than typing module imports.
    
    Q8: How would you handle log rotation?
    A8: Check multiple files: graphql_test.log, graphql_test.log.1, etc.
        Aggregate entries from all rotation files.
    
    Q9: What if JSON parsing is slow?
    A9: Use ijson for streaming JSON parsing, or orjson for faster
        parsing. For test files, standard json module is fine.
    
    Q10: How does STRATA handle logs at scale?
    A10: Sends logs to centralized system (Splunk, ELK). Tests validate
         log format, production monitoring validates log ingestion.
    """
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
            # ignore non-json lines (debug output, stack traces, etc.)
            continue
    return out


def wait_for_log_event(event: str, request_id: Optional[str] = None, timeout_s: float = 3.0) -> dict:
    """
    Poll the log file until a specific event appears, supporting asynchronous logging.
    
    How It Works:
    1. Records start time for timeout calculation
    2. Enters polling loop (checks every 0.1 seconds)
    3. Reads all log lines on each iteration
    4. Searches in reverse (newest first) for matching event
    5. Optionally filters by request_id for correlation
    6. Returns matched log entry or raises AssertionError on timeout
    
    Why We Do This:
    Logging is often asynchronous (written in background thread/process).
    Between request completion and log file write, there's a small delay.
    
    Without polling:
    - Tests would race: "log entry not found" fails happen randomly
    - Flaky tests erode confidence in test suite
    - Can't distinguish "logging broken" from "logging delayed"
    
    Polling solves this by:
    - Allowing time for async operations to complete
    - Failing deterministically after timeout (real failures)
    - Making tests resilient to system load variations
    
    Critical Pattern: In distributed systems, eventual consistency is
    common. Tests must accommodate asynchronous side effects.
    
    Args:
        event: Event type to search for (e.g., "graphql_request", "graphql_error")
        request_id: Optional request ID for correlation filtering
        timeout_s: Maximum seconds to wait before failing (default: 3.0)
        
    Returns:
        dict: Matching log entry
        
    Raises:
        AssertionError: If event not found within timeout period
        
    Q&A:
    
    Q1: Why 0.1 second sleep interval?
    A1: Balances responsiveness (tests complete quickly when log appears)
        with CPU usage (not spinning constantly). Adjust based on system.
    
    Q2: Why search in reverse (newest first)?
    A2: Recent events more likely to be what we're looking for. Optimization
        for common case where event was just logged.
    
    Q3: What if multiple events match?
    A3: Returns first match (most recent). If you need all matches,
        modify to return list instead of single entry.
    
    Q4: Why default timeout of 3 seconds?
    A4: Conservative but not excessive. Async logging usually completes
        in <100ms, but CI environments under load may be slower.
    
    Q5: How do you debug timeouts?
    A5: Error message includes last 5 log entries. Shows what WAS logged,
        helps identify mismatched event names or request IDs.
    
    Q6: What if log file is appended during search?
    A6: Race condition! Next iteration will see new entries. Polling
        naturally handles this - no special synchronization needed.
    
    Q7: Why AssertionError instead of custom exception?
    A7: pytest treats AssertionError as test failure (expected).
        Custom exceptions appear as errors (unexpected), confusing reports.
    
    Q8: Could you use inotify or file watchers?
    A8: Yes, more efficient! But adds complexity and platform dependencies
        (inotify is Linux-only). Polling is simple and cross-platform.
    
    Q9: How do you test this helper function?
    A9: Mock read_json_log_lines to return controlled data. Verify
        correct entry is found, timeout is enforced, filtering works.
    
    Q10: What's the STRATA equivalent?
    A10: Log aggregation systems with query APIs. Instead of polling files,
         query Splunk/ELK: "find logs where request_id=X in last 3 seconds".
    """
    start = time.time()
    while time.time() - start < timeout_s:
        entries = read_json_log_lines()
        for e in reversed(entries):  # Start from most recent
            if e.get("event") != event:
                continue
            if request_id and e.get("request_id") != request_id:
                continue
            return e
        time.sleep(0.1)
    
    # Timeout reached - provide helpful error message
    raise AssertionError(
        f"Did not find log event='{event}' request_id='{request_id}' within {timeout_s}s. "
        f"Last 5 log entries: {read_json_log_lines()[-5:]}"
    )


@pytest.fixture(autouse=True)
def ensure_log_dir():
    """
    Ensure logs directory exists before any test runs.
    
    How It Works:
    1. autouse=True means this fixture runs automatically for every test
    2. Creates 'logs' directory if it doesn't exist
    3. exist_ok=True prevents errors if directory already exists
    4. No yield/return means it's setup-only (no teardown)
    
    Why We Do This:
    Tests write to logs/graphql_test.log. If logs/ directory doesn't exist,
    logging fails and tests error out with "FileNotFoundError: logs/".
    
    This fixture prevents that by ensuring the directory structure exists
    before any test attempts to write logs.
    
    Alternative approaches:
    - Create directory in server startup code (but tests shouldn't depend on server)
    - Manual mkdir in test suite setup (but easy to forget)
    - autouse fixture is cleanest (automatic, no test code changes needed)
    
    Design Pattern: "Ensure Preconditions" fixture. Makes test environment
    ready without requiring explicit calls in every test.
    
    Returns:
        None: Setup-only fixture, no value provided to tests
        
    Q&A:
    
    Q1: Why autouse instead of explicit fixture parameter?
    A1: Every test needs the directory. autouse avoids boilerplate of
        adding ensure_log_dir parameter to every test function.
    
    Q2: What's the scope of this fixture?
    A2: Function scope (default). Runs once per test. Could be session scope
        since directory only needs creating once, but function is safer.
    
    Q3: Why not create directory in conftest.py module-level code?
    A3: Fixtures are pytest's recommended way. They're discoverable,
        composable, and appear in test reports.
    
    Q4: What if directory creation fails (permissions)?
    A4: Test suite fails immediately with clear error. Better than
        mysterious failures later when trying to write logs.
    
    Q5: Should this clear old log files?
    A5: Could! Add: if LOG_PATH.exists(): LOG_PATH.unlink()
        Ensures clean state per test. Trade-off: can't debug previous runs.
    
    Q6: Why exist_ok=True instead of checking if directory exists first?
    A6: Cleaner code. exist_ok=True is atomic and race-condition safe
        (multiple processes can call it simultaneously).
    
    Q7: How do you test this fixture?
    A7: Delete logs/ directory, run test, verify directory exists afterward.
        Or mock os.makedirs, verify it's called with correct parameters.
    
    Q8: What if you need different log directories per test?
    A8: Make this a parametrized fixture or add test-specific subdirectories:
        os.makedirs(f"logs/{request.node.name}", exist_ok=True)
    
    Q9: Could this be a session-scoped fixture?
    A9: Yes! More efficient (runs once per test session). Safe because
        directory creation is idempotent (creating twice doesn't break anything).
    
    Q10: How does STRATA handle test artifacts?
    A10: Likely uses temporary directories (tmpdir fixture), CI artifact
         storage, or container volumes that are automatically cleaned up.
    """
    os.makedirs("logs", exist_ok=True)


@pytest.mark.observability
def test_graphql_logs_request_id_and_duration_success():
    """
    Test that successful GraphQL requests log correlation ID and execution time.
    
    Scenario:
    Execute a simple introspection query and verify:
    1. Server returns X-Request-Id in response header
    2. Log entry exists with matching request_id
    3. Log contains operation metadata (name, type)
    4. Duration is measured and logged as integer milliseconds
    
    How It Works:
    1. Execute GraphQL introspection query (low risk of failure)
    2. Verify response is successful (200 OK with data)
    3. Extract X-Request-Id from response headers
    4. Poll log file for matching graphql_request event
    5. Validate log entry structure and content
    
    Why This Matters for STRATA:
    Request correlation is MANDATORY in microservices architectures.
    When a request flows through multiple services:
    - Each service logs with the same request_id
    - Distributed traces can be reconstructed
    - Debugging becomes possible (follow request through all services)
    - Performance bottlenecks can be identified (which service is slow?)
    
    Without correlation IDs:
    - Logs from different services can't be connected
    - "Which user request caused this error?" is unanswerable
    - Multi-service debugging is impossible
    - Incident resolution takes hours instead of minutes
    
    This test validates the "happy path" - successful requests are properly
    instrumented with observability metadata.
    
    Expected Behavior:
    - Response header: X-Request-Id: <some-uuid>
    - Log entry: {
        "event": "graphql_request",
        "request_id": "<same-uuid>",
        "operation_name": "IntrospectMe",
        "operation_type": "query",
        "duration_ms": 5
      }
    
    Q&A:
    
    Q1: Why use introspection query instead of real data query?
    A1: Introspection is built-in, always available, never fails.
        Eliminates variables (data setup, permissions) to focus on observability.
    
    Q2: What if server doesn't generate request_id?
    A2: Test fails at "assert rid". Acceptable - middleware MUST provide
        correlation IDs. No request_id = observability contract violated.
    
    Q3: Why assert duration_ms >= 0 instead of > 0?
    A3: Extremely fast operations might complete in <1ms and round to 0.
        Asserting >= 0 prevents false failures while catching negative values (bugs).
    
    Q4: What's the difference between operation_name and operation_type?
    A4: Name: developer-assigned ("IntrospectMe"). Type: query/mutation/subscription.
        Both are useful for logging and debugging.
    
    Q5: Why "unknown" as valid operation_type?
    A5: Malformed queries might not parse. "unknown" is better than crashing.
        Tests accept it, monitoring can alert on high "unknown" rates.
    
    Q6: Should duration_ms have an upper bound assertion?
    A6: Optional. Could add: assert duration_ms < 1000 (under 1 second).
        But CI under load might violate this, causing flaky tests.
    
    Q7: What if multiple requests have same request_id?
    A7: Serious bug! UUIDs should be unique. Monitoring would detect this
        through duplicate request_id count metrics.
    
    Q8: How do you verify request_id format (UUID)?
    A8: Could add: assert re.match(r'^[0-9a-f-]{36}$', rid)
        Validates structure. But any unique string is acceptable.
    
    Q9: Why wait_for_log_event instead of directly reading logs?
    A9: Async logging means delay between request completion and log write.
        Polling handles this timing issue gracefully.
    
    Q10: How would STRATA extend this test?
    A10: Validate OpenTelemetry span IDs, check trace context propagation,
         verify integration with APM (DataDog/Dynatrace), and test
         correlation across multiple backend services.
    """
    q = 'query IntrospectMe { __type(name: "Query") { fields { name } } }'
    r = gql(q, operation_name="IntrospectMe")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body

    # Validate correlation ID in response header
    rid = r.headers.get("X-Request-Id")
    assert rid, "Expected X-Request-Id header from server"

    # Validate structured logging with correlation
    log = wait_for_log_event("graphql_request", request_id=rid)
    assert log["request_id"] == rid
    assert log["operation_name"] == "IntrospectMe"
    assert log["operation_type"] in ("query", "mutation", "unknown")
    assert isinstance(log["duration_ms"], int)
    assert log["duration_ms"] >= 0


@pytest.mark.observability
def test_graphql_respects_incoming_x_request_id():
    """
    Test that server propagates client-provided correlation IDs.
    
    Scenario:
    Client sends X-Request-Id header with custom value.
    Verify server uses that value (doesn't generate new one).
    
    How It Works:
    1. Generate known correlation ID
    2. Send in X-Request-Id header with GraphQL request
    3. Verify server returns SAME ID in response header
    4. Verify server logs with SAME ID
    
    Why This Matters for STRATA:
    In microservices, requests flow through multiple hops:
    Frontend → API Gateway → STRATA → Backend Services
    
    Each hop must propagate the SAME correlation ID:
    - Frontend generates ID
    - Gateway forwards it
    - STRATA forwards it
    - Backend services use it
    
    Without propagation:
    - Each service generates different ID
    - Distributed traces break (can't connect logs)
    - Request flow becomes untraceable
    
    This tests "ID propagation contract" - middleware must respect
    incoming correlation IDs, not replace them.
    
    Real-World Example:
    User reports error. Support finds frontend request_id in browser logs.
    Uses that ID to search all service logs. Requires propagation to work.
    
    Expected Behavior:
    - Request header: X-Request-Id: test-request-id-12345
    - Response header: X-Request-Id: test-request-id-12345 (SAME)
    - Log entry: request_id: test-request-id-12345 (SAME)
    
    Q&A:
    
    Q1: What if client sends invalid request_id (empty string)?
    A1: Server should generate new ID. Could test this:
        headers={"X-Request-Id": ""} should result in non-empty response header.
    
    Q2: Why test both header AND log propagation?
    A2: Two separate concerns: HTTP layer (headers) and logging layer (structured logs).
        Both must work for full observability.
    
    Q3: What if server modifies the ID (adds prefix)?
    A3: Breaks correlation! Test would fail. Some systems do this for
        namespace separation, but should be documented behavior.
    
    Q4: Should request_id have format validation?
    A4: Optional. Some systems enforce UUID format. But strings are more
        flexible (hex, base64, custom formats all work).
    
    Q5: What if multiple X-Request-Id headers are sent?
    A5: HTTP spec: use first one. Server should validate and reject
        multiple headers or join them. Test edge case.
    
    Q6: How do you test case-insensitive header names?
    A6: Send X-request-id (lowercase). HTTP headers are case-insensitive.
        Server must handle both.
    
    Q7: Why "test-request-id-12345" format?
    A7: Human-readable for debugging. Production uses UUIDs but tests
        benefit from recognizable IDs.
    
    Q8: What if server accepts but doesn't log the ID?
    A8: Test fails at wait_for_log_event. Catches "header works but logging
        broken" scenario.
    
    Q9: How do you test ID propagation across multiple services?
    A9: Integration test: send request to frontend, verify same ID appears
        in all service logs. Requires test environment with multiple services.
    
    Q10: How does STRATA handle correlation differently?
    A10: Likely uses W3C Trace Context standard (traceparent header) for
         compatibility with OpenTelemetry and other observability tools.
    """
    incoming = "test-request-id-12345"
    q = 'query MyOp { __type(name: "Query") { name } }'
    r = gql(q, operation_name="MyOp", headers={"X-Request-Id": incoming})
    assert r.status_code == 200

    # Verify propagation in response header
    assert r.headers.get("X-Request-Id") == incoming
    
    # Verify propagation in structured logs
    log = wait_for_log_event("graphql_request", request_id=incoming)
    assert log["request_id"] == incoming
    assert log["operation_name"] == "MyOp"


@pytest.mark.observability
def test_graphql_logs_operation_type_mutation():
    """
    Test that mutations are correctly identified and logged as "mutation" type.
    
    Scenario:
    Execute a mutation (createPet) and verify operation_type is "mutation",
    not "query" or "unknown".
    
    How It Works:
    1. Execute createPet mutation with valid data
    2. Verify mutation succeeds (no errors)
    3. Extract correlation ID from response
    4. Find log entry for this request
    5. Verify operation_type field is "mutation"
    
    Why This Matters for STRATA:
    Different operation types have different characteristics:
    - Queries: read-only, cacheable, can retry safely
    - Mutations: write operations, NOT cacheable, retry = duplicate action
    - Subscriptions: long-lived connections, different error handling
    
    Monitoring systems need to track these separately:
    - Query latency vs mutation latency (different SLOs)
    - Mutation error rates (more critical than query errors)
    - Cache hit rates (queries only)
    
    Without operation_type:
    - Can't distinguish read vs write performance
    - Can't alert on "high mutation failure rate"
    - Caching strategies become impossible
    
    This tests "operation classification" - middleware must correctly
    identify operation types for proper instrumentation.
    
    Expected Behavior:
    - Log entry: {
        "operation_name": "CreatePetOp",
        "operation_type": "mutation",  ← NOT "query" or "unknown"
        ...
      }
    
    Q&A:
    
    Q1: How does server determine operation_type?
    A1: Parses GraphQL document, identifies operation keyword (query/mutation).
        GraphQL libraries (ariadne, apollo) provide this info.
    
    Q2: What if document has both query and mutation?
    A2: operationName specifies which to execute. Server logs type of
        executed operation, not all operations in document.
    
    Q3: Why verify "errors" not in response?
    A3: Ensures test data is valid. If mutation fails, operation_type might
        still be logged, but we want to test successful mutation path.
    
    Q4: What about subscriptions?
    A4: Separate test! Subscriptions use WebSocket protocol, different
        testing approach. This tests HTTP-based queries and mutations only.
    
    Q5: How do you test "unknown" operation_type?
    A5: Send malformed query that can't be parsed:
        gql("notvalid syntax $%^") should log operation_type="unknown"
    
    Q6: Why assert "mutation" exactly instead of in ("mutation", "query")?
    A6: Specificity. Test verifies correct classification. Generic assertion
        would miss misclassification bugs (mutation logged as query).
    
    Q7: What if mutation is introspection (__type)?
    A7: Introspection is always query type (read-only). Server should
        correctly identify even when sent via mutation syntax.
    
    Q8: How do you test nested mutations?
    A8: GraphQL doesn't support nested mutations syntactically. Each
        mutation field executes sequentially, all logged as "mutation".
    
    Q9: Should tests verify mutation side effects persisted?
    A9: Separate concern. This test focuses on observability (logging).
        Functional tests verify data persistence.
    
    Q10: How does STRATA use operation_type?
    A10: Separate metrics dashboards (query vs mutation), different
         SLO thresholds, and operation-specific error handling and retries.
    """
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
    """
    Test that GraphQL errors are logged with structured metadata.
    
    Scenario:
    Send malformed query that will fail. Verify:
    1. Server returns errors in response body (not crash)
    2. Error event is logged separately (graphql_error)
    3. Log entry contains error details in structured format
    
    How It Works:
    1. Send query with non-existent field (definitelyNotARealField)
    2. Verify server returns GraphQL errors (not 500 crash)
    3. Extract correlation ID for log lookup
    4. Find graphql_error log entry
    5. Verify error messages are logged as structured array
    
    Why This Matters for STRATA:
    Error logging is often neglected in observability. But errors are
    MOST important to log properly because they indicate problems.
    
    Structured error logging enables:
    - Error rate tracking (how many errors per minute?)
    - Error categorization (validation vs system errors)
    - Correlation with specific requests (which user hit this error?)
    - Root cause analysis (what was the query that failed?)
    
    Without structured error logging:
    - Errors are lost in general logs (needle in haystack)
    - Can't alert on error rate spikes
    - Can't distinguish user errors from system errors
    - Debugging requires manual log grepping
    
    This tests "error observability" - failures must be instrumented
    as thoroughly as successes.
    
    Expected Behavior:
    - Response: { "errors": [{"message": "Field not found", ...}] }
    - Log entry: {
        "event": "graphql_error",
        "request_id": "...",
        "operation_name": "BadOne",
        "errors": ["Field not found"]
      }
    
    Q&A:
    
    Q1: Why accept status 200 OR 400?
    A1: GraphQL convention: 200 with errors in body is valid. Some
        servers use 400 for client errors. Both are acceptable.
    
    Q2: Why separate graphql_error event instead of including in graphql_request?
    A2: Allows different log levels (ERROR vs INFO), easier to filter
        errors in log aggregation systems.
    
    Q3: What types of errors should be logged?
    A3: Validation errors (field not found), authentication/authorization
        errors, resolver exceptions, timeout errors. All errors.
    
    Q4: Should error messages be sanitized?
    A4: Yes! Don't log sensitive data (passwords, tokens). Tests should
        verify error messages don't contain secrets.
    
    Q5: Why verify errors is list with len >= 1?
    A5: GraphQL can return multiple errors (multiple validation failures).
        Test accepts any count > 0.
    
    Q6: What if error message is empty string?
    A6: Invalid! Tests verify: isinstance(m, str) and m (non-empty).
        Empty errors are useless for debugging.
    
    Q7: How do you test stack traces are logged?
    A7: Check log entry for "stack_trace" field. Production should log
        stack traces for unexpected errors, not validation errors.
    
    Q8: Should error codes be logged?
    A8: Yes! Error codes (NOT_FOUND, UNAUTHORIZED) enable programmatic
        error handling. Tests could verify log["error_codes"].
    
    Q9: What about error severity levels?
    A9: Validation errors: WARN. System errors: ERROR. Critical: CRITICAL.
        Log entry should include severity for proper alerting.
    
    Q10: How does STRATA categorize errors?
    A10: Error taxonomy: client errors (4xx), server errors (5xx),
         downstream errors, timeout errors. Each category has different
         SLOs and alerting thresholds.
    """
    bad_query = "query BadOne { definitelyNotARealField }"
    r = gql(bad_query, operation_name="BadOne")
    assert r.status_code in (200, 400)
    body = r.json()
    assert "errors" in body and body["errors"]

    rid = r.headers.get("X-Request-Id")
    assert rid

    # Find error event log entry
    log = wait_for_log_event("graphql_error", request_id=rid)
    assert log["operation_name"] == "BadOne"
    
    # Verify errors are logged as structured data
    assert isinstance(log.get("errors"), list) and len(log["errors"]) >= 1
    
    # Verify error messages are non-empty strings
    assert any(isinstance(m, str) and m for m in log["errors"])


@pytest.mark.observability
def test_graphql_duration_is_reasonable():
    """
    Test that duration measurements are reasonable and within expected bounds.
    
    Scenario:
    Execute fast query (introspection) and verify duration is:
    1. Integer type (not float or string)
    2. Non-negative (0 or greater)
    3. Under reasonable upper bound (5000ms = 5 seconds)
    
    How It Works:
    1. Execute simple query expected to complete quickly
    2. Extract duration_ms from log entry
    3. Validate type and range
    
    Why This Matters for STRATA:
    Performance monitoring depends on accurate duration measurement.
    If durations are:
    - Wrong type: metrics dashboards break
    - Negative: calculation bugs
    - Excessive: performance regressions go unnoticed
    
    Duration measurement enables:
    - Latency percentiles (p50, p95, p99)
    - Performance SLO tracking (95% of requests under 100ms)
    - Regression detection (new deploy increased latency 2x)
    - Capacity planning (how many requests can system handle?)
    
    Without duration logging:
    - Can't identify slow operations
    - Can't track performance trends over time
    - Can't alert on latency SLO violations
    - Can't optimize bottlenecks
    
    This tests "performance instrumentation" - durations must be
    captured accurately and in usable format.
    
    Expected Behavior:
    - Log entry: { "duration_ms": 15, ... }
        Type: int (not "15" or 15.7)
        Range: 0 <= duration < 5000
    
    Q&A:
    
    Q1: Why milliseconds instead of seconds?
    A1: Milliseconds provide better precision for fast operations (<1s).
        Standard unit for API latency measurement.
    
    Q2: Why allow 0ms duration?
    A2: Extremely fast operations (cache hits, no-op queries) can complete
        in <1ms and round to 0. Better than rejecting valid data.
    
    Q3: Why 5000ms upper bound?
    A3: Introspection should be fast (<100ms typically). 5000ms is very
        conservative to avoid flaky tests in slow CI environments.
    
    Q4: Should this test verify database query time separately?
    A4: Advanced: log separate db_duration_ms. Allows distinguishing
        network latency vs database latency vs business logic.
    
    Q5: What if duration is negative?
    A5: Major bug! Clock skew or timing logic error. Test would fail,
        catching serious instrumentation bug.
    
    Q6: How do you handle clock adjustments?
    A6: Use monotonic clocks (time.monotonic() in Python) instead of
        wall clocks. Immune to NTP adjustments.
    
    Q7: Should tests verify duration for mutations too?
    A7: Yes! Separate test with mutation. Mutations typically slower
        (database writes) so different upper bound.
    
    Q8: What about client-side timing?
    A8: Separate metric! Client measures end-to-end (including network).
        Server measures processing time. Both are valuable.
    
    Q9: How do you test timing under load?
    A9: Performance tests with concurrent requests. Verify p95 latency
        stays under threshold even at high QPS.
    
    Q10: How does STRATA track performance?
    A10: Histogram metrics (latency distribution), distributed tracing
         (span durations per service), and synthetic monitoring (simulated
         user requests from different regions).
    """
    q = 'query QuickCheck { __type(name: "Query") { name } }'
    r = gql(q, operation_name="QuickCheck")
    assert r.status_code == 200

    rid = r.headers.get("X-Request-Id")
    assert rid

    log = wait_for_log_event("graphql_request", request_id=rid)
    
    # Verify duration is integer type (not string or float)
    assert isinstance(log["duration_ms"], int)
    
    # Verify duration is in reasonable range
    assert 0 <= log["duration_ms"] < 5000, \
        f"Duration {log['duration_ms']}ms is outside expected range [0, 5000)"


# ==============================================================================
# COMPREHENSIVE Q&A ABOUT OBSERVABILITY TESTING
# ==============================================================================

"""
GENERAL OBSERVABILITY TESTING Q&A:

Q1: What is observability?
A1: The ability to understand system internal state from external outputs
    (logs, metrics, traces). Goes beyond monitoring (which is just alerting).

Q2: What's the difference between logging, metrics, and traces?
A2: Logs: discrete events with context. Metrics: aggregated numbers over time.
    Traces: request flow across services. All three are needed for full observability.

Q3: Why test observability instead of just functionality?
A3: Observability is a requirement, not a nice-to-have. Systems without
    observability are undebuggable in production. Tests prevent regressions.

Q4: What's the difference between correlation ID and trace ID?
A4: Correlation ID: business/request identifier (spans single request).
    Trace ID: technical identifier (spans request + all downstream calls).

Q5: How do you test log aggregation system integration?
A5: Mock log forwarder, verify logs are sent in correct format.
    Or integration test: verify logs appear in actual Splunk/ELK.

Q6: What's structured logging?
A6: Logging in machine-parseable format (JSON) instead of free-form text.
    Enables querying, filtering, aggregation by log aggregation systems.

Q7: How do you prevent sensitive data in logs?
A7: Tests verify logs don't contain: passwords, tokens, SSNs, credit cards.
    Use regex patterns to search for sensitive data patterns.

Q8: What's the 3 pillars of observability?
A8: Logs (events), Metrics (numbers), Traces (request flow). Sometimes
    called LMT. Comprehensive observability needs all three.

Q9: How do you test performance SLOs?
A9: Load tests with performance assertions: assert p95_latency < 100ms.
    Or use performance monitoring tools (DataDog, Dynatrace).

Q10: What's the difference between instrumentation and observability?
A10: Instrumentation: adding telemetry to code (logging, metrics, tracing).
     Observability: using that telemetry to understand system behavior.
     Instrumentation enables observability.
"""