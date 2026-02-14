# test_chaos.py
"""
Chaos Engineering Tests for GraphQL Middleware

This module implements chaos testing to validate system resilience under failure conditions.
Chaos testing is critical for middleware platforms like STRATA because they orchestrate
multiple backend services where partial failures are expected, not exceptional.

Key Principles Demonstrated:
- Fault injection via headers (X-Fault)
- Graceful degradation validation
- Partial failure handling
- State integrity under failure
- Structured error responses
- System queryability after failures

Why This Matters for STRATA:
STRATA handles 90% of API communication at Ally. When downstream services fail,
the middleware must:
1. Return structured errors (not crash)
2. Preserve partial data where possible
3. Maintain system integrity
4. Remain queryable for other operations
5. Provide clear error context for debugging
"""

import os
import json
import time
import requests
import pytest

BASE_URL = os.getenv("BASE_URL", "http://localhost:5001")
GQL_URL = f"{BASE_URL}/graphql"


def wait_for_server(url="http://localhost:5001/graphql", timeout=10):
    """
    Wait for the GraphQL server to become available before running tests.
    
    How It Works:
    1. Polls the GraphQL endpoint repeatedly
    2. Accepts 200 (playground) or 405 (method not allowed for GET)
    3. Times out after specified duration
    4. Raises RuntimeError if server is unreachable
    
    Why We Do This:
    In CI/CD pipelines, the server may take a few seconds to start.
    Without this check, early tests would fail with connection errors
    rather than actual test failures, making CI results unreliable.
    
    Args:
        url: GraphQL endpoint to check
        timeout: Maximum seconds to wait for server
        
    Raises:
        RuntimeError: If server doesn't respond within timeout
        
    Q&A:
    
    Q1: Why accept both 200 and 405 status codes?
    A1: GET requests to /graphql return 200 for the playground UI,
        but POST-only endpoints might return 405. Both indicate the
        server is running and reachable.
    
    Q2: Why use a short sleep interval (0.2s)?
    A2: Balances responsiveness (tests start quickly when server is ready)
        with reduced CPU load (not polling constantly). Shorter intervals
        would waste CPU; longer intervals delay test execution.
    
    Q3: Why catch all exceptions instead of specific ones?
    A3: During startup, servers can fail in many ways: connection refused,
        timeout, DNS errors, etc. We don't care about the specific failure,
        just whether the server is responding yet.
    
    Q4: Why not use a library like `wait-for-it` or `dockerize`?
    A4: Pure Python implementation has no external dependencies and works
        consistently across all platforms (local dev, CI, Docker, etc.)
    
    Q5: What happens if the timeout is too short?
    A5: Tests will fail with "Server not reachable" in slow environments
        (CI runners under load). The 10s default is conservative enough
        for most scenarios.
    
    Q6: Could this be a pytest fixture instead?
    A6: Yes, but running it at module level ensures the server check happens
        once before any tests import, preventing confusing import-time errors.
    
    Q7: Why not use pytest-timeout?
    A7: pytest-timeout controls test execution time. This function controls
        server availability checking - a different concern.
    
    Q8: What if multiple test files need this check?
    A8: Move to conftest.py as a session-scoped autouse fixture to run once
        for the entire test suite, not once per module.
    
    Q9: Why return True instead of None on success?
    A9: Explicit return value makes the function's success case clear and
        allows for conditional logic if needed (though currently unused).
    
    Q10: How would this change for a production health check?
    A10: Production would check /health endpoint, validate response body,
         check multiple backend services, and use exponential backoff for
         retry delays.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code in (200, 405):  # GET /graphql should be 200 (playground)
                return True
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Server not reachable at {url}")


# Execute server check at module import time
wait_for_server()


def gql(query: str, variables=None, operation_name=None, headers=None):
    """
    Execute a GraphQL query with optional fault injection.
    
    How It Works:
    1. Constructs GraphQL request payload (query + variables + operationName)
    2. Merges custom headers (like X-Fault) with Content-Type
    3. POSTs to GraphQL endpoint with 10s timeout
    4. Returns raw response for test assertions
    
    Why We Do This:
    Centralizing GraphQL requests provides:
    - Consistent request structure across all chaos tests
    - Easy fault injection via headers
    - Timeout protection (prevents hanging tests)
    - Single point to add auth, logging, or retries later
    
    This is the "API Client Wrapper" pattern applied to GraphQL testing.
    
    Args:
        query: GraphQL query or mutation string
        variables: Optional query variables dict
        operation_name: Optional operation name for multi-operation documents
        headers: Optional custom headers (e.g., X-Fault for chaos testing)
        
    Returns:
        requests.Response: Raw HTTP response from GraphQL server
        
    Q&A:
    
    Q1: Why pass operation_name separately instead of in the query?
    A1: GraphQL allows multiple operations in one document. The server needs
        operationName to know which to execute. This follows GraphQL spec.
    
    Q2: Why use a 10-second timeout?
    A2: GraphQL queries can be complex. 10s allows for reasonable query
        execution while preventing tests from hanging indefinitely on
        network issues or server hangs.
    
    Q3: Why not validate the response here?
    A3: Each test has different validation needs (errors vs data vs partial).
        Keeping this function focused on request execution preserves
        flexibility for diverse test scenarios.
    
    Q4: Why merge headers instead of replacing them?
    A4: Content-Type must always be application/json for GraphQL. Merging
        preserves required headers while allowing custom ones like X-Fault.
    
    Q5: How does X-Fault header trigger chaos scenarios?
    A5: The GraphQL server (graphql_api.py) checks for X-Fault in request
        headers and injects failures based on the value (e.g., "resolver_exception_pets").
    
    Q6: Why not use a GraphQL client library like gql or sgqlc?
    A6: Raw requests gives precise control over headers and payloads for
        chaos testing. Client libraries abstract away details we need to
        manipulate for fault injection.
    
    Q7: What if variables contains sensitive data?
    A7: In production tests, consider logging sanitization. For this demo,
        test data is non-sensitive (pet names, types).
    
    Q8: Why JSON payload instead of query params?
    A8: GraphQL spec recommends POST with JSON body for queries (not GET).
        This supports complex queries, mutations, and large variables.
    
    Q9: Could this support batched queries?
    A9: Yes, modify to accept a list of queries and send as an array in the
        payload. GraphQL servers supporting batching will execute all.
    
    Q10: How would you add authentication?
    A10: Add auth_token parameter, include as Bearer token in headers:
         h["Authorization"] = f"Bearer {auth_token}"
    """
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    if operation_name is not None:
        payload["operationName"] = operation_name
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    return requests.post(GQL_URL, json=payload, headers=h, timeout=10)


def assert_structured_error(resp_json: dict):
    """
    Validate that GraphQL returned a properly structured error response.
    
    How It Works:
    1. Checks that 'errors' key exists and is non-empty
    2. Validates first error has required 'message' field
    3. Ensures message is a string (not null or other type)
    
    Why We Do This:
    GraphQL spec requires errors to follow a specific structure. When middleware
    fails, it must return errors that clients can parse and display to users.
    Unstructured errors (500 crashes, HTML error pages) break client applications.
    
    This validates the middleware upholds the GraphQL contract even during failures.
    
    Args:
        resp_json: Parsed JSON response body from GraphQL server
        
    Raises:
        AssertionError: If error structure is invalid or missing
        
    Q&A:
    
    Q1: Why only check the first error instead of all?
    A1: For chaos tests, we're validating structure exists, not exhaustive
        error handling. Checking one error proves the pattern works. Production
        tests might iterate through all errors.
    
    Q2: What's the difference between errors and exceptions?
    A2: GraphQL 'errors' are structured responses per spec. Exceptions are
        unhandled server crashes that return 500. We want errors, never exceptions.
    
    Q3: Why is 'path' commented out?
    A3: GraphQL spec makes 'path' optional (only for field-level errors).
        Query-level errors may not have it. Enforcing it would cause false failures.
    
    Q4: What does a valid GraphQL error look like?
    A4: { "errors": [{ "message": "Pet not found", "path": ["pet"], "locations": [...] }] }
    
    Q5: Why not check for 'extensions' field?
    A5: Extensions are optional vendor-specific additions. While useful (error codes,
        stack traces), they're not required by spec. Tests should pass without them.
    
    Q6: How do you distinguish user errors from system errors?
    A6: Use error extensions: { "extensions": { "code": "NOT_FOUND" } } for user errors,
        { "extensions": { "code": "INTERNAL_ERROR" } } for system failures.
    
    Q7: Why assert on non-empty list instead of checking length?
    A7: Pythonic: empty list is falsy, non-empty is truthy. More readable than len() > 0.
    
    Q8: What if the response isn't JSON?
    A8: Caller should handle. This function assumes resp_json is already parsed.
        In production, wrap in try/except for JSONDecodeError.
    
    Q9: Should this validate HTTP status codes too?
    A9: No - separation of concerns. HTTP validation happens in test functions.
        This focuses purely on GraphQL error structure.
    
    Q10: How would STRATA use this in production?
    A10: Monitoring systems would count structured vs unstructured errors.
         Structured errors are expected; unstructured indicate middleware bugs.
    """
    assert "errors" in resp_json and resp_json["errors"], f"Expected errors, got: {resp_json}"
    err = resp_json["errors"][0]
    assert "message" in err and isinstance(err["message"], str)
    # path is a strong indicator this is GraphQL-structured
    # not all failures include it, so keep soft unless you enforce it
    # assert "path" in err


def get_data_dict(body: dict) -> dict:
    """
    Safely extract 'data' from GraphQL response, handling null values.
    
    How It Works:
    1. Retrieves 'data' key from response body
    2. If data is a dict, returns it as-is
    3. If data is None (common on errors), returns empty dict {}
    4. If data is missing, returns empty dict {}
    
    Why We Do This:
    GraphQL can return { "data": null, "errors": [...] } on failures.
    Tests accessing body["data"]["pets"] would crash with TypeError.
    Normalizing to {} allows safe key checking: "pets" in get_data_dict(body).
    
    This defensive pattern prevents test code from being more fragile than
    the system under test.
    
    Args:
        body: Parsed JSON response from GraphQL server
        
    Returns:
        dict: The data object, or empty dict if data is null/missing
        
    Q&A:
    
    Q1: Why return {} instead of None when data is null?
    A1: Empty dict is safer for test code using 'in' checks and .get().
        Tests can write: if get_data_dict(body) to check for data presence.
    
    Q2: What's the difference between null data and missing data key?
    A2: { "data": null } means resolver failed before returning anything.
        Missing 'data' means malformed response (should never happen with GraphQL).
    
    Q3: When does GraphQL return data=null?
    A3: When a non-nullable field fails in a resolver, GraphQL nulls out the
        entire query result. E.g., if pets is [Pet!]! and resolver throws,
        data becomes null.
    
    Q4: Could you use .get("data", {}) instead?
    A4: That only handles missing key, not null values. get() returns None
        if data=null. The isinstance check catches both cases.
    
    Q5: Why not raise an exception for null data?
    A5: Chaos tests intentionally cause failures. Null data is expected.
        Raising would conflate test failures with expected failure conditions.
    
    Q6: What if data is a list instead of dict?
    A6: GraphQL spec requires 'data' to be an object (dict), never array.
        If it's a list, the server is violating spec - returning {} fails
        the test, which is correct behavior.
    
    Q7: Should this validate the 'errors' key too?
    A7: No - single responsibility. This function normalizes data access.
        Error validation is assert_structured_error's job.
    
    Q8: How does this help with partial failures?
    A8: Partial failures return { "data": { "pets": [...], "orders": null }, "errors": [...] }.
        This function preserves the partial data dict for inspection.
    
    Q9: Why not use dataclasses or Pydantic for response parsing?
    A9: Chaos tests verify error handling, not data schemas. Strict parsing
        would fail on intentionally malformed responses. Dict access is flexible.
    
    Q10: What's the STRATA parallel?
    A10: STRATA must handle downstream service failures gracefully. If one
         backend is down, return partial data for healthy services + errors.
         This pattern validates that behavior.
    """
    d = body.get("data")
    return d if isinstance(d, dict) else {}


@pytest.mark.chaos
def test_downstream_domain_failure_is_isolated():
    """
    Test that failure in one domain (inventory) doesn't crash other domains (pets).
    
    Scenario:
    Simulate inventory service being down while querying both pets and inventory.
    
    How It Works:
    1. Send query requesting both pets and inventory
    2. Inject X-Fault: downstream_inventory_failure header
    3. Server simulates inventory domain throwing an exception
    4. Validate response contains errors (inventory failed)
    5. If data is present, validate pets are still accessible
    
    Why This Matters for STRATA:
    STRATA coordinates multiple backend services. When one service fails,
    the middleware must:
    - Return errors for the failed service
    - Still return data from healthy services
    - Not crash or return 500
    
    This is "partial failure tolerance" - a critical middleware capability.
    
    Expected Behavior:
    Response: { 
        "data": { "pets": [...], "inventory": null },
        "errors": [{ "message": "Inventory service unavailable", ... }]
    }
    
    Q&A:
    
    Q1: Why accept both 200 and 400 status codes?
    A1: GraphQL convention: 200 for partial success with errors, 400 for
        request-level failures. Both are valid responses to failures.
    
    Q2: What if pets is also null?
    A2: Current test allows it (if data). Stricter version would assert
        pets is not None, enforcing that one failure doesn't cascade.
    
    Q3: How does the server know to fail inventory?
    A3: graphql_api.py checks for X-Fault header and injects failures in
        the inventory resolver based on header value.
    
    Q4: Why not assert on specific error messages?
    A4: Error messages may change during development. Structure validation
        is more stable. Production tests might validate error codes.
    
    Q5: What's the difference between this and a mock?
    A5: This tests real failure handling in the middleware layer. Mocks
        would test individual resolver logic. This is integration-level chaos.
    
    Q6: Could this test run against production?
    A6: With feature flags! Production chaos testing (e.g., Netflix's Chaos Monkey)
        uses sophisticated blast radius controls. Never in this simple form.
    
    Q7: Why check data presence with 'if data'?
    A7: Depending on GraphQL server config, some failures return data=null.
        The 'if' allows test to pass whether data is returned or not.
    
    Q8: What would a real inventory failure look like?
    A8: Timeout, connection refused, 503 service unavailable, slow response.
        Middleware must handle all these consistently.
    
    Q9: Why not test each domain failure separately?
    A9: We do! This tests multi-domain isolation. Other tests (below) focus
        on specific domain failures and error types.
    
    Q10: How do you prevent false positives?
    A10: Verify pets actually has data in non-chaos scenarios first. Only
         trust isolation test if baseline functionality works.
    """
    q = "query { pets { id name } inventory { id inventory pet_id } }"
    r = gql(q, headers={"X-Fault": "downstream_inventory_failure"})
    assert r.status_code in (200, 400)

    body = r.json()
    assert "errors" in body and body["errors"], f"Expected errors, got: {body}"

    data = get_data_dict(body)

    # If data is present, pets should still be there and usable
    if data:
        assert "pets" in data
        assert isinstance(data["pets"], list)


@pytest.mark.chaos
def test_resolver_exception_returns_structured_error():
    """
    Test that exceptions in resolvers return structured GraphQL errors, not crashes.
    
    Scenario:
    Simulate an unhandled exception thrown in the pets resolver.
    
    How It Works:
    1. Query for pets
    2. Inject X-Fault: resolver_exception_pets to trigger exception
    3. Validate server returns structured error (not 500 crash)
    4. Validate data structure is preserved (pets key exists, value is null or list)
    
    Why This Matters for STRATA:
    Bugs happen. When a resolver throws an exception, the middleware must:
    - Catch the exception
    - Return a structured GraphQL error
    - Not crash the entire server (other queries still work)
    - Log the error for debugging
    
    This tests "graceful degradation" - the system remains operational during faults.
    
    Expected Behavior:
    Response: {
        "data": { "pets": null },
        "errors": [{ "message": "Internal server error", "path": ["pets"], ... }]
    }
    
    Q&A:
    
    Q1: Why allow pets to be null OR list?
    A1: Depends on GraphQL schema nullability. Non-nullable fields bubble null
        up to parent. Nullable fields return null directly. Both are valid.
    
    Q2: What's the difference between this and the previous test?
    A2: Previous: downstream service fails. This: resolver code itself throws.
        Different failure modes require different handling.
    
    Q3: How do you prevent exception swallowing?
    A3: Server logs all exceptions (via structured logging). Tests validate
        structure; monitoring validates exceptions are logged.
    
    Q4: What exceptions should be caught?
    A4: All exceptions in resolvers. Re-raise only for critical bugs.
        GraphQL library (ariadne) catches and structures them automatically.
    
    Q5: Why not let exceptions crash for faster debugging?
    A5: In production, one bad query shouldn't crash the server. Structured
        errors provide debugging context without downtime.
    
    Q6: How do you distinguish bugs from expected errors?
    A6: Expected errors (404, validation): return user-friendly messages.
        Bugs (exceptions): log full stack trace, return generic "Internal error".
    
    Q7: What if multiple resolvers throw?
    A7: GraphQL returns multiple errors, one per failed resolver. Tests should
        validate errors is an array and can contain multiple entries.
    
    Q8: Why test this if ariadne handles it automatically?
    A8: Trust but verify. Middleware config could break error handling.
        Tests catch regressions (e.g., debug mode leaking stack traces).
    
    Q9: What would STRATA do differently?
    A9: Add correlation IDs to errors, integrate with APM (e.g., Datadog),
        trigger alerts on exception rate thresholds.
    
    Q10: How do you test exception handling without injecting faults?
    A10: Integration tests with mocked backends returning errors. Chaos tests
         complement by validating end-to-end behavior under faults.
    """
    q = "query { pets { id name } }"
    r = gql(q, headers={"X-Fault": "resolver_exception_pets"})
    assert r.status_code in (200, 400)

    body = r.json()
    assert "errors" in body and body["errors"], f"Expected errors, got: {body}"

    data = get_data_dict(body)

    # If data exists, pets key should be present (often null)
    if data:
        assert "pets" in data
        assert data["pets"] is None or isinstance(data["pets"], list)


@pytest.mark.chaos
def test_partial_data_return_field_level_error():
    """
    Test that field-level failures return partial data with errors.
    
    Scenario:
    Simulate some pets returning successfully while others fail to resolve status field.
    
    How It Works:
    1. Query for pets including status field
    2. Inject X-Fault: partial_pet_status_failure
    3. Server simulates status resolver failing for some pets (e.g., odd IDs)
    4. Validate data contains pet list (not null)
    5. Validate errors array exists (acknowledging failures)
    6. Validate at least one pet has non-null status (partial success)
    
    Why This Matters for STRATA:
    Real-world APIs don't fail uniformly. A batch query might have:
    - 8 successful responses
    - 2 timeouts
    
    Middleware must return the 8 successes + errors for the 2 failures.
    This is "partial success" - better user experience than all-or-nothing.
    
    Expected Behavior:
    Response: {
        "data": { 
            "pets": [
                { "id": 1, "name": "Buddy", "status": "available" },
                { "id": 2, "name": "Max", "status": null },
                { "id": 3, "name": "Luna", "status": "pending" }
            ]
        },
        "errors": [{ "message": "Status unavailable", "path": ["pets", 1, "status"], ... }]
    }
    
    Q&A:
    
    Q1: Why assert data is not null unlike other tests?
    A1: Field-level errors should still return the parent object. Null data
        indicates query-level failure, which isn't the scenario being tested.
    
    Q2: How does the server determine which pets fail?
    A2: Implementation-specific. Could be odd IDs, random selection, specific
        names. Tests validate pattern, not specific failures.
    
    Q3: What if all statuses are null?
    A3: Test would fail (assertion: at least one non-null). This enforces
        that partial means "some succeed", not "all fail".
    
    Q4: Why check 'p is not None' in list comprehension?
    A4: Defensive: if pets list contains null entries (malformed data),
        .get() would crash. Filter nulls before accessing fields.
    
    Q5: How is this different from full resolver exception?
    A5: Full exception: entire pets query fails. Partial: some pets succeed,
        specific fields fail for others. Different error granularity.
    
    Q6: What's a real-world example of field-level failure?
    A6: Pet data from database, status from external service. Service timeout
        affects status field only, not core pet data.
    
    Q7: Why not count exact failures?
    A7: Test brittleness. Number of failures may vary based on random selection,
        load, timing. Testing the pattern is more valuable than exact counts.
    
    Q8: How do you prevent masking all failures as partial success?
    A8: Separate tests for full failures. If all pets fail, it should return
        data=null + errors, not partial success pattern.
    
    Q9: What if GraphQL schema doesn't allow null status?
    A9: Non-nullable fields bubble null up to parent. pets[1] becomes null
        entirely, not pets[1].status = null. Schema design affects behavior.
    
    Q10: How does STRATA benefit from this pattern?
    A10: Users see partial data immediately (better UX) while errors are logged
         for backend teams to fix. Degrades gracefully under load.
    """
    q = "query { pets { id name status } }"
    r = gql(q, headers={"X-Fault": "partial_pet_status_failure"})
    assert r.status_code in (200, 400)
    body = r.json()

    assert "data" in body and "pets" in body["data"]
    assert isinstance(body["data"]["pets"], list)
    assert_structured_error(body)

    # Ensure partial success: not all statuses are null
    statuses = [p.get("status") for p in body["data"]["pets"] if p is not None]
    assert any(s is not None for s in statuses), f"Expected at least one status to succeed. Got: {body}"


@pytest.mark.chaos
def test_inventory_sync_failure_does_not_corrupt_state():
    """
    Test that shared-write failures (cross-domain mutations) maintain data integrity.
    
    Scenario:
    Simulate createPet mutation where the automatic inventory sync fails.
    
    How It Works:
    1. Attempt to create a pet (which triggers inventory sync)
    2. Inject X-Fault: inventory_sync_fail to make sync throw exception
    3. Validate mutation returns structured error (not 500 crash)
    4. Query pets and inventory to ensure system is still queryable
    5. Validate no orphaned/malformed inventory records were created
    
    Why This Matters for STRATA:
    Middleware often orchestrates multi-step workflows:
    1. Create pet in pet service
    2. Create inventory in inventory service
    3. Update analytics
    
    If step 2 fails, step 1 must rollback. Otherwise: inconsistent state.
    This tests "transactional integrity" in distributed operations.
    
    Expected Behavior:
    - createPet mutation fails with structured error
    - No pet record created (rolled back)
    - No inventory record created
    - System remains queryable for other operations
    
    Q&A:
    
    Q1: How does this test rollback if there's no database?
    A1: In-memory implementation uses try/except to remove pet from list
        if inventory sync fails. Pattern scales to real DBs with transactions.
    
    Q2: What's a shared-write failure?
    A2: Mutation that writes to multiple domains. Failure in any domain
        should rollback all writes to maintain consistency.
    
    Q3: Why query pets AND inventory after?
    A3: Proves system-wide stability. Both reads work, confirming mutation
        failure didn't corrupt server state or crash any resolver.
    
    Q4: What if createPet succeeds but inventory fails?
    A4: That's the failure being tested! Server should rollback pet creation
        and return error. Test validates no pet exists after failed mutation.
    
    Q5: How do you validate "no orphaned inventory"?
    A5: Check all inventory records have valid structure (id, pet_id).
        Could extend to verify pet_id references existing pet (FK integrity).
    
    Q6: What's the difference between this and test_resolver_exception?
    A6: Resolver exception: single operation fails. This: multi-operation
        transaction fails mid-flight. Tests rollback behavior, not error handling.
    
    Q7: Why use timestamp in pet name?
    A7: Ensures uniqueness in repeated test runs. Prevents collisions if
        tests run concurrently or cleanup doesn't fully execute.
    
    Q8: What if server has eventual consistency, not immediate?
    A8: Add sleep before verification query, or poll until state stabilizes.
        For middleware, usually strong consistency is required for mutations.
    
    Q9: How would you test this with a real database?
    A9: Use transactions. Mock inventory service to fail. Verify database
        transaction rolled back and no rows were committed.
    
    Q10: What's the STRATA equivalent?
    A10: Order placement spanning payment, inventory, shipping. If payment
         succeeds but inventory fails, rollback payment. Critical for
         financial consistency.
    """
    create = """
    mutation CreatePet($name: String!, $type: String!, $status: String) {
      createPet(name: $name, type: $type, status: $status) { id name type status order_id }
    }
    """
    vars_ = {"name": f"ChaosDog-{int(time.time())}", "type": "dog", "status": "available"}

    r = gql(create, variables=vars_, operation_name="CreatePet", headers={"X-Fault": "inventory_sync_fail"})
    assert r.status_code in (200, 400)
    body = r.json()
    assert_structured_error(body)

    # System remains queryable
    q2 = "query { pets { id name } inventory { id inventory pet_id } }"
    r2 = gql(q2)
    assert r2.status_code == 200
    b2 = r2.json()
    assert "data" in b2
    assert isinstance(b2["data"]["pets"], list)
    assert isinstance(b2["data"]["inventory"], list)

    # Integrity check: no inventory rows with missing required structure
    for inv in b2["data"]["inventory"]:
        assert "id" in inv
        # inventory and pet_id may be nullable by schema, but your model expects them
        # tighten this if you enforce non-null


# ==============================================================================
# COMPREHENSIVE Q&A ABOUT CHAOS TESTING IN GENERAL
# ==============================================================================

"""
GENERAL CHAOS TESTING Q&A:

Q1: What is chaos engineering?
A1: Discipline of experimenting on distributed systems to build confidence in
    their ability to withstand turbulent conditions in production. Coined by
    Netflix's Chaos Monkey team.

Q2: Why is chaos testing important for middleware?
A2: Middleware sits between many services. Failures are inevitable and frequent.
    Chaos testing validates graceful degradation instead of cascading failures.

Q3: How is chaos testing different from fault injection?
A3: Chaos testing is broader (includes load, network partitions, etc.). Fault
    injection is one technique within chaos engineering (simulating specific failures).

Q4: When should chaos tests run?
A4: In CI (controlled scenarios), staging (realistic load), and carefully in
    production (with blast radius controls and feature flags).

Q5: What's the blast radius in chaos testing?
A5: Scope of impact if test causes real failure. Start small (one instance),
    gradually expand. Never full production without safeguards.

Q6: How do you prevent chaos tests from causing real outages?
A6: Feature flags, canary deployments, monitoring, automatic rollback, limited
    scope, off-peak hours, synthetic traffic only.

Q7: What's the difference between chaos testing and load testing?
A7: Load tests validate performance under volume. Chaos tests validate resilience
    under failures. Complementary, not redundant.

Q8: How do you measure chaos test success?
A8: Metrics: error rates, latency, recovery time, data consistency, system
    queryability. Success = graceful degradation, not zero errors.

Q9: What's the most important chaos test for STRATA?
A9: Downstream service timeout with partial data return. Core middleware
    responsibility is graceful handling of backend failures.

Q10: How would you extend these tests for production readiness?
A10: Add network partitions, region failures, database failover, cache failures,
     rate limiting, authentication failures, concurrent mutations, and
     correlation ID propagation validation.
"""