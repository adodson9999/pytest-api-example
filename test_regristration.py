from jsonschema.exceptions import ValidationError
import jsonschema
import pytest
import schemas
import api_helpers
from api_helpers import make_request
from hamcrest import assert_that, contains_string, is_
import uuid
from typing import Any, Dict, List, Optional, Tuple

'''
TODO: Finish this test by...
1) Troubleshooting and fixing the test failure
The purpose of this test is to validate the response matches the expected schema defined in schemas.py
'''

SCHEMA_RESOURCES = [
    ("Pet", "/pets/1", schemas.pet),
    ("Customer", "/customer/1", schemas.customer),
    ("Inventory", "/inventory/1", schemas.inventory),
    ("Vet", "/vet/1", schemas.vet),
    ("Vendor", "/vendor/1", schemas.vendor),
    ("Event", "/event/1", schemas.event),
    ("Trainer", "/trainers/1", schemas.trainer),
]

@pytest.mark.parametrize("label, endpoint, schema", SCHEMA_RESOURCES)
def test_get_by_id_schema(label, endpoint, schema):
    """
    Purpose:  Verifies that every GET-by-ID (or list-of-one) endpoint returns data
              that conforms to its expected JSON Schema.

    Why we do it this way:
    - Parametrized over SCHEMA_RESOURCES → one test definition covers all resources
      (pets, orders, inventory, vendors, customers, events, trainers, etc.) without duplication.
    - Checks multiple layers:
      1. HTTP 200 + correct Content-Type (application/json)
      2. Response is parseable JSON (and not empty if list)
      3. Shape is a dict (normalizes list-of-one → first item)
      4. Full jsonschema validation with very detailed failure output
    - Uses jsonschema.validate → catches structural mismatches early (missing required fields,
      wrong types, extra forbidden properties, enum violations, etc.)
    - Produces extremely helpful pytest failure messages → includes exact validation path,
      offending value, full response → makes debugging schema mismatches fast
    - Assumes endpoints are single-item (by ID) or return [single-item] → common pattern
      in many REST APIs when fetching one resource

    How it works:
    - Parametrized by (label, endpoint, schema) tuples from SCHEMA_RESOURCES
    - Makes GET request via api_helpers.make_request
    - Asserts basics (status, content-type)
    - Parses JSON, normalizes if wrapped in list
    - Runs jsonschema.validate → fails with rich context on mismatch

    This is a high-value regression / contract test — catches backend schema drift
    or frontend/backend mismatch very early.
    """
    response = api_helpers.make_request("GET", endpoint)
    # Basic HTTP checks with useful debug output
    assert response.status_code == 200, (
        f"Expected 200 OK from {endpoint} ({label}), got {response.status_code}. "
        f"Response body: {response.text}"
    )
    content_type = response.headers.get("Content-Type", "")
    assert "application/json" in content_type.lower(), (
        f"Expected JSON response Content-Type for {endpoint} ({label}), got: {content_type}"
    )
    # Parse JSON and normalize shape (some endpoints mistakenly return a list)
    data = response.json()
    if isinstance(data, list):
        assert len(data) > 0, f"Expected non-empty list response from {endpoint} ({label})"
        data = data[0]
    assert isinstance(data, dict), (
        f"Expected JSON object for single {label} at {endpoint}, got {type(data)}: {data}"
    )
    # Validate against schema and produce a clear failure message if invalid
    try:
        jsonschema.validate(instance=data, schema=schema)
    except ValidationError as e:
        pytest.fail(
            f"Response JSON does not match '{label}' schema:\n"
            f"Endpoint: {endpoint}\n"
            f"Validation message: {e.message}\n"
            f"Validator: {e.validator}\n"
            f"Validator path: {list(e.schema_path)}\n"
            f"Instance path: {list(e.path)}\n"
            f"Offending instance: {e.instance}\n"
            f"Full response: {data}"
        )


# 10 follow-up questions & short answers

# 1. Why normalize list responses to first item instead of failing if it's a list?
#    → Some endpoints return [single-item] even for GET-by-ID (legacy or inconsistency) — this makes the test more forgiving without losing coverage.

# 2. Why assert len(data) > 0 when it's a list, but not require exactly len==1?
#    → Defensive — allows accidental multi-item responses during dev, but still ensures something came back. Can tighten to ==1 later if needed.

# 3. Should we add a check that the list has exactly one item?
#    → Yes — good idea for stricter contract. Change to assert len(data) == 1 if you know the API should never return multiples here.

# 4. Why use jsonschema.validate instead of pydantic or custom validators?
#    → jsonschema is lightweight, standard, and produces excellent error paths/paths — perfect for test-time validation without model classes.

# 5. Why pytest.fail instead of letting ValidationError propagate?
#    → Gives fully customized, human-readable failure message with all context (paths, instance, full body) — much better than raw traceback.

# 6. What if the endpoint requires authentication or query params?
#    → Assumes these are public / no-auth endpoints for schema check. If auth needed → add headers=... to make_request or use a fixture.

# 7. Why check "application/json" in lower() instead of exact match?
#    → Some servers add charset=utf-8 → "application/json; charset=utf-8" — lower() + in makes it robust.

# 8. Should we also validate that no extra unknown properties exist?
#    → Depends on schema: if schema has additionalProperties: false → jsonschema already enforces it. If not → add it to schemas.

# 9. Can we make this test run against a specific ID instead of whatever the endpoint returns?
#    → Yes — if you want deterministic data, create a fresh resource first (like in other tests) and GET /{id}.

# 10. Why no timeout or retry handling here like in make_request?
#     → api_helpers.make_request already has timeout/retries inside (assuming it's the httpx version). No need to duplicate.


'''
TODO: Finish this test by...
1) Extending the parameterization to include all available statuses
2) Validate the appropriate response code
3) Validate the 'status' property in the response is equal to the expected status
4) Validate the schema for each object in the response
'''

# All available statuses per your PET_STATUS enum
@pytest.mark.parametrize("status", ["available", "sold", "pending"])
def test_find_by_status_200(status):
    """
    Purpose:  Verifies that the /pets/findByStatus endpoint correctly filters pets
              by each valid status value and returns properly shaped data.

    Why we do it this way:
    - Parametrized over the three known valid pet statuses → tests the filter behavior
      exhaustively for each enum value without duplicating code.
    - Uses api_helpers.make_request with params → clean, reusable, and consistent with
      the rest of the suite (retries, timeout, verify=False if configured there).
    - Checks multiple layers in sequence:
      1. HTTP 200 success
      2. Response is a JSON list (array)
      3. Each item is a dict/object
      4. Every pet has exactly the requested status (proves filtering works)
      5. Every pet conforms to the pet schema (structural + type + required fields)
    - Uses jsonschema.validate per item → catches schema drift or invalid data early
    - Detailed failure messages include status + body → makes debugging fast when
      backend returns wrong status, empty list, or malformed objects
    - Aligns with Swagger Petstore spec — this is one of the canonical filter endpoints

    How it works:
    - pytest runs the test once for each status ("available", "sold", "pending")
    - Sends GET /pets/findByStatus?status=<value>
    - Asserts basics → parses → loops over results → checks status match + schema

    This test is a strong contract + regression check for the most common pet query use-case.
    """
    response = api_helpers.make_request("GET", "/pets/findByStatus", params={"status": status})
    # 2) Validate the appropriate response code
    assert response.status_code == 200, (
        f"Expected 200 for status={status}, got {response.status_code}. "
        f"Body: {response.text}"
    )
    data = response.json()
    # Endpoint should return a list of pets
    assert isinstance(data, list), f"Expected list response for status={status}, got {type(data)}"
    # 3) Validate the 'status' property in each object matches expected status
    # 4) Validate the schema for each object in the response
    for pet in data:
        assert isinstance(pet, dict), f"Each item should be an object/dict, got {type(pet)}: {pet}"
        assert pet.get("status") == status, (
            f"Expected pet.status == {status}, got {pet.get('status')}. Pet: {pet}"
        )
        jsonschema.validate(instance=pet, schema=schemas.pet)


# 10 follow-up questions & short answers

# 1. Why only test the three statuses — what about invalid ones like "unknown"?
#    → Invalid statuses are (or should be) covered in a separate negative test (e.g. 400/422)

# 2. Why not assert len(data) > 0 for each status?
#    → Some statuses might legitimately return empty lists (e.g. no sold pets yet) — forcing >0 would flake

# 3. Should we check that the list contains unique IDs or no duplicates?
#    → Possible — but out of scope here; belongs in a separate deduplication/quality test

# 4. Why use pet.get("status") instead of pet["status"]?
#    → Safer — avoids KeyError if "status" is missing (schema validation will catch it anyway)

# 5. Can we parametrize more statuses if the API adds new ones (e.g. "reserved")?
#    → Yes — just add to the list in @pytest.mark.parametrize; test auto-expands

# 6. Why validate schema on every pet instead of just the first one?
#    → Ensures consistency — backend might return valid first item but malformed later ones

# 7. What if the endpoint returns a wrapped response like {"pets": [...]}?
#    → Current code would fail on isinstance(data, list) — add normalization if that happens

# 8. Should we also validate that no pet has a status different from requested?
#    → Implicitly done — if any pet.status != requested, the assert fails

# 9. Why no sorting/order check on the returned list?
#    → Not specified in Swagger spec — usually order is undefined unless ?sort=... is used

# 10. Can we make this test create pets with specific statuses first for determinism?
#     → Yes — stronger test. Current version relies on pre-existing data (common in Petstore examples)

'''
TODO: Finish this test by...
1) Testing and validating the appropriate 404 response for /pets/{pet_id}
2) Parameterizing the test for any edge cases
'''

# 1) Validate appropriate 404 for /pets/{pet_id}
# 2) Parameterize for edge cases
RESOURCES = [
    ("Pet", "/pets"),
    ("Customer", "/customer"),
    ("Inventory", "/inventory"),
    ("Vet", "/vet"),
    ("Vendor", "/vendor"),
    ("Event", "/event"),
    ("Trainer", "/trainers"),
]

TEST_IDS = [0, -1, 999999999, "does-not-exist"]


@pytest.mark.parametrize("label, base_path", RESOURCES)
@pytest.mark.parametrize("item_id", TEST_IDS)
def test_get_by_id_404(label, base_path, item_id):
    """
    Purpose:  Verifies that attempting to GET a non-existent resource by ID returns
              the correct 404 Not Found status across all resource types.

    Why we do it this way:
    - Double parametrized:
      - First level: over RESOURCES (label + base_path pairs) → covers every resource type
        (pets, orders, inventory, vendors, customers, events, trainers, etc.) in one test definition
      - Second level: over TEST_IDS (typically invalid/non-existent IDs like -1, 999999, "invalid", UUIDs, etc.)
        → tests multiple "not found" scenarios without hardcoding IDs
    - Produces a Cartesian product → many combinations (e.g. 8 resources × 5 test IDs = 40 executions)
      with very little code → high coverage, low maintenance
    - Uses api_helpers.make_request → consistent with suite (retries, timeout, verify=False if configured)
    - Single focused assertion: status_code == 404
    - Extremely detailed failure message → includes label, ID, full endpoint, status, and body
      → makes it trivial to debug when backend returns 200/500/403 instead of 404
    - No schema/content validation → pure negative status test (existence check)
    - Assumes TEST_IDS contains values guaranteed not to exist (negative numbers, huge positives,
      malformed strings, etc.) → deterministic "not found" behavior

    How it works:
    - pytest generates one test call per (label, base_path) × item_id combination
    - Constructs endpoint = /<base_path>/<item_id> (e.g. /pets/999999, /orders/-1)
    - Sends GET request
    - Asserts exactly 404 + rich debug output on failure

    This is a critical negative test — ensures proper resource-not-found handling
    across the entire API surface.
    """
    endpoint = f"{base_path}/{item_id}"
    response = api_helpers.make_request("GET", endpoint)
    assert response.status_code == 404, (
        f"Expected 404 for {label} id={item_id} at {endpoint}, got {response.status_code}. "
        f"Body: {response.text}"
    )


# 10 follow-up questions & short answers

# 1. Why double @pytest.mark.parametrize instead of one big list of tuples?
#    → Cleaner code + better test naming in output (shows label and item_id separately)

# 2. What happens if TEST_IDS includes an ID that actually exists?
#    → Test fails (gets 200 instead of 404) → good signal to remove that ID from TEST_IDS

# 3. Should we also check the response body/message contains "not found"?
#    → Nice to have for stronger contract — add assert "not found" in response.text.lower()

# 4. Why no Content-Type check (e.g. application/json)?
#    → Many APIs return 404 with text/plain or HTML error pages — keeping it minimal here

# 5. Can we add a check for 404 vs 400 on malformed IDs (e.g. strings on numeric routes)?
#    → Yes — but belongs in a separate test (e.g. test_get_by_id_invalid_format_400)

# 6. Why not create-and-delete a resource then GET it to prove 404 after deletion?
#    → That would be stronger (lifecycle test) — but this version is simpler and faster (no setup/teardown)

# 7. What if some resources use UUIDs instead of integers — do TEST_IDS cover that?
#    → If TEST_IDS includes invalid UUID strings (e.g. "not-a-uuid"), yes — otherwise add UUID-specific invalid cases

# 8. Should we test very large IDs (e.g. 2**64-1) for overflow bugs?
#    → Possible — add to TEST_IDS if backend is vulnerable to int64 overflow

# 9. Why no timeout/retry handling specific to this test?
#    → api_helpers.make_request already includes it — no need to duplicate unless you want shorter timeout for 404s

# 10. Can we mark this test with @pytest.mark.xfail for resources that don't return 404?
#     → Yes — if some endpoints intentionally return 200 {} or 410 Gone — but better to fix backend or separate test

# -----------------------------
# Resource configuration
# -----------------------------
RESOURCES = [
    {
        "label": "Pet",
        "base": "/pets",
        "make_payload": lambda: {"name": f"Pet-{uuid.uuid4().hex[:8]}", "type": "dog", "status": "available"},
    },
    {
        "label": "Customer",
        "base": "/customer",
        "make_payload": lambda: {
            "name": f"Cust-{uuid.uuid4().hex[:8]}",
            "date": "2026-02-13",
            "purchase": 1,
            "email": f"cust-{uuid.uuid4().hex[:8]}@example.com",
        },
    },
    {
        "label": "Inventory",
        "base": "/inventory",
        "make_payload": lambda: {"inventory": 10},
    },
    {
        "label": "Vet",
        "base": "/vet",
        "make_payload": lambda: {
            "name": f"Vet-{uuid.uuid4().hex[:8]}",
            "contact_form": "email",
            "contact_info": 1234567890,
        },
    },
    {
        "label": "Vendor",
        "base": "/vendor",
        "make_payload": lambda: {
            "name": f"Vendor-{uuid.uuid4().hex[:8]}",
            "contact_form": "email",
            "contact_info": "vendor@example.com",
            "point_of_contact": "Alex",
            "product": 1,
        },
    },
    {
        "label": "Event",
        "base": "/event",
        "make_payload": lambda: {
            "name": f"Event-{uuid.uuid4().hex[:8]}",
            "date": "2026-03-01",
            "location": 101,
        },
    },
    {
        "label": "Trainer",
        "base": "/trainers",
        "make_payload": lambda: {
            "name": f"Trainer-{uuid.uuid4().hex[:8]}",
            "contact_form": "text",
            "contact_info": 9998887777,
        },
    },
]


INVALID_INT_IDS = [0, -1, 999999999]
NON_NUMERIC_ID = "does-not-exist"


# -----------------------------
# Helper utilities
# -----------------------------
def _list_all(base: str):
    """
    Purpose:  Convenience wrapper that sends a GET request to the list/collection
              endpoint of a given resource (e.g. GET /pets/, /orders/, /vendors/).

    Why we do it this way:
    - Centralizes the list endpoint pattern (always {base}/) → reduces duplication
      across many tests that need to fetch the full collection.
    - Returns the raw response object → callers can inspect status_code, headers,
      .json(), .text, etc. flexibly.
    - Uses api_helpers.make_request → inherits retries, timeout, verify=False,
      logging, and any future improvements (e.g. auth headers, base URL prefix).
    - No assertions here → keeps helper dumb/pure; assertions belong in the tests
      that use it (better separation of concerns and clearer failure messages).

    Returns: the httpx.Response object from the GET request
    """
    resp = api_helpers.make_request("GET", f"{base}/")
    return resp


# 10 follow-up questions & short answers for _list_all

# 1. Why return the full Response instead of resp.json()?
#    → Callers often need status_code, headers, or raw text for different assertions

# 2. Should we add params= support (e.g. ?limit=10&offset=0)?
#    → Yes — easy extension: def _list_all(base: str, params=None): … make_request(…, params=params)

# 3. Why no assert resp.status_code == 200 inside the helper?
#    → Helpers should not assert — that belongs in the specific test (different tests expect different codes)

# 4. What if the backend uses /list or /all instead of trailing / ?
#    → Then update the f-string or make it configurable in RESOURCES dict

# 5. Can we cache responses for repeated calls in the same test?
#    → Possible with @lru_cache — but risky (state leakage); better to refetch for isolation

# 6. Should we log the URL being requested?
#    → api_helpers.make_request already prints on errors/retries — can add debug print if needed

# 7. Why not raise on non-2xx here?
#    → Keeps helper reusable for negative tests (404, 500, etc.)

# 8. Can we make it generic for any HTTP method?
#    → Yes — refactor to _request(method, base, path="/", **kwargs) if many methods needed

# 9. What if base already ends with / — does it become // ?
#    → Most servers normalize it fine; can use f"{base.rstrip('/')}/" to clean

# 10. Should we return resp.json() if status 200, else raise?
#     → No — keeps it simple; json() parsing can fail on non-JSON errors


def _create_item(base: str, payload: dict):
    """
    Purpose:  Convenience wrapper that sends a POST request to create a new item
              in the given resource collection (e.g. POST /pets/ with JSON body).

    Why we do it this way:
    - Abstracts the common create pattern ({base}/ + POST + json=payload)
      → reduces boilerplate in creation-heavy tests.
    - Returns the raw response → callers can check status (201/200), parse .json(),
      verify Location header, etc.
    - Uses api_helpers.make_request → consistent retries, timeout, insecure handling.
    - No assertions inside → allows reuse in both happy-path (expect 201) and negative
      tests (expect 400 on bad payload).

    Returns: the httpx.Response object from the POST request
    """
    return api_helpers.make_request("POST", f"{base}/", json=payload)


# 10 follow-up questions & short answers for _create_item

# 1. Why not return resp.json() directly?
#    → Some tests need status_code or headers first; parsing can fail on error responses

# 2. Should we support files= for multipart uploads (e.g. pet photo)?
#    → Yes — add files=None param and pass to make_request if needed later

# 3. Why no auto-check for 201 Created?
#    → Different APIs return 200 or 201 on create — assertion belongs in test

# 4. Can we add headers= param (e.g. for auth)?
#    → Yes — def _create_item(…, headers=None): … make_request(…, headers=headers)

# 5. What if payload is invalid — should helper raise?
#    → No — let test assert 400/422; keeps helper reusable

# 6. Should we generate a unique name/ID in payload automatically?
#    → Better done in test — keeps helper generic

# 7. Why f"{base}/" instead of f"{base}"?
#    → Most REST APIs expect trailing slash on collection POST

# 8. Can we extract created ID automatically if present?
#    → Possible — but overkill; most tests do resp.json()["id"]

# 9. What if server returns Location header with new URL?
#    → Test can check resp.headers.get("Location") after call

# 10. Should we retry only on 5xx or also on 429 rate-limit?
#     → Depends on make_request impl — usually only connection errors; can extend


def _get_by_id(base: str, item_id):
    """
    Purpose:  Convenience wrapper that fetches a single resource by ID
              (e.g. GET /pets/123, /orders/456).

    Why we do it this way:
    - Standardizes the by-ID pattern ({base}/{item_id}) → used heavily in
      positive/negative GET-by-ID tests.
    - Returns raw response → flexible for asserting 200 + schema, 404, 403, etc.
    - Uses api_helpers.make_request → inherits all robustness features.
    - No assertions → reusable for both success and not-found cases.

    Returns: the httpx.Response object from the GET request
    """
    return api_helpers.make_request("GET", f"{base}/{item_id}")


# 10 follow-up questions & short answers for _get_by_id

# 1. Why not accept item_id as str/int and coerce?
#    → Caller already knows type; keeps helper simple

# 2. Should we handle UUID vs int IDs differently?
#    → No need — endpoint handles string interpolation fine

# 3. What if item_id is None or empty string?
#    → Test would GET /base/ → probably 404 or 405; test can assert

# 4. Can we add params= for query filters on single item?
#    → Rare for GET-by-ID — but easy to add params=None param

# 5. Why no auto .json() return?
#    → Some tests need .status_code or .headers first

# 6. Should we raise if status != 200?
#    → No — used in 404 tests too

# 7. What if base ends with / — becomes //id ?
#    → Servers usually normalize; can rstrip('/') if paranoid

# 8. Can we extract and return (resp, resp.json())?
#    → Possible — but current raw response is more flexible

# 9. Why not cache by (base, item_id) for repeated calls?
#    → Risk of stale data; better refetch for test isolation

# 10. Should we validate item_id type (int/str)?
#     → Not necessary — backend will reject invalid format with 400/404


# -----------------------------
# 1) LIST endpoint tests
# 7 resources * 4 tests = 28 tests
# -----------------------------

@pytest.mark.parametrize("r", RESOURCES)
def test_list_returns_200(r):
    """
    Purpose:  Verifies that the list endpoint for each resource returns HTTP 200 OK.

    Why we do it this way:
    - Parametrized over RESOURCES → one test definition covers all resource types
    - Uses _list_all helper → clean, consistent, reusable
    - Simple focused assertion on status_code == 200
    - Rich failure message includes label + full body → fast debug when backend 500s or 403s
    - Part of basic smoke/contract suite — every collection should be listable

    This generates 7 tests (one per resource) — quick baseline health check.
    """
    resp = _list_all(r["base"])
    assert resp.status_code == 200, f"{r['label']} list should be 200. Body: {resp.text}"


# 10 follow-up questions & short answers for test_list_returns_200

# 1. Why no check for empty list vs non-empty?
#    → Some collections can be legitimately empty — separate test if needed

# 2. Should we assert no 401/403 (auth issues)?
#    → Implicit — if 401/403 occurs, fails anyway; add explicit if auth required

# 3. Why not check total count header or pagination metadata?
#    → Out of scope — belongs in pagination/compliance tests

# 4. Can we mark some resources xfail if list is not implemented?
#    → Yes — @pytest.mark.xfail(reason="List not supported yet") on specific cases

# 5. Why use r["base"] instead of hardcoding paths?
#    → DRY + easy to add/remove resources via RESOURCES list

# 6. Should we add a timeout assert (response took < 2s)?
#    → Possible with time.perf_counter() around call — good perf regression check

# 7. What if backend returns 204 No Content for empty list?
#    → Test fails — decide if 204 is acceptable and update assertion

# 8. Can we combine this with test_list_returns_json in one test?
#    → Yes — but separate tests give clearer failure isolation

# 9. Why no schema validation here?
#    → Schema check belongs in separate test (e.g. test_list_items_match_schema)

# 10. Should we test with ?limit=0 or ?offset=999?
#     → Separate pagination/edge-case tests — this is basic happy path


@pytest.mark.parametrize("r", RESOURCES)
def test_list_returns_json(r):
    """
    Purpose:  Ensures every resource list endpoint returns proper JSON content type.

    Why we do it this way:
    - Parametrized over RESOURCES → uniform coverage
    - Checks Content-Type header contains "application/json" (case-insensitive)
    - Detailed failure message shows actual Content-Type → catches text/html, application/problem+json, etc.
    - Complements test_list_returns_200 — HTTP basics first

    Simple but catches misconfigured content negotiation early.
    """
    resp = _list_all(r["base"])
    assert "application/json" in resp.headers.get("Content-Type", "").lower(), (
        f"{r['label']} list should return JSON. Content-Type: {resp.headers.get('Content-Type')}"
    )


# 10 follow-up questions & short answers for test_list_returns_json

# 1. Why .lower() + "in" instead of exact == "application/json"?
#    → Servers often add "; charset=utf-8" — makes test robust

# 2. What if server returns application/json-seq or application/hal+json?
#    → Fails — decide if acceptable; can add "json" in lower()

# 3. Should we check for charset=utf-8 specifically?
#    → Optional — most modern APIs assume UTF-8; rarely worth enforcing

# 4. Why no check when status != 200?
#    → If 500 returns text/html — still good to know; but can guard with if resp.status_code == 200

# 5. Can we assert no other Content-Types (e.g. exclude text/plain)?
#    → Not needed — "application/json" in header is sufficient

# 6. What if header is missing?
#    → resp.headers.get() returns "" → fails correctly

# 7. Should this test run even on 404/500 responses?
#    → Current code does — can add guard if only care about 200

# 8. Why not validate JSON parseability here too?
#    → Separate test (test_list_returns_list_type) already does resp.json()

# 9. Can we snapshot the Content-Type per resource?
#    → Overkill — current assert is enough

# 10. What if API uses Accept header negotiation?
#     → Test sends no Accept → assumes default is JSON; can add Accept header if needed


@pytest.mark.parametrize("r", RESOURCES)
def test_list_returns_list_type(r):
    """
    Purpose:  Confirms that every resource list endpoint returns a JSON array (list).

    Why we do it this way:
    - Parametrized over RESOURCES → consistent coverage
    - First ensures 200 (re-asserted for safety)
    - Parses JSON and checks isinstance(data, list)
    - Clear failure message shows type received → catches dict, str, int, etc.
    - Basic structural check — most list endpoints must return []

    This test + schema validation on items (separate test) gives strong contract.
    """
    resp = _list_all(r["base"])
    assert resp.status_code == 200, f"{r['label']} list should be 200. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, list), f"{r['label']} list should return a list, got {type(data)}"


# 10 follow-up questions & short answers for test_list_returns_list_type

# 1. Why re-assert status_code == 200 here?
#    → Defensive — makes test self-contained; fails early if previous test setup broke

# 2. Should we allow tuple or set as well?
#    → No — JSON spec says array → list is correct expectation

# 3. What if endpoint returns {"items": [...]} wrapper?
#    → Fails → add data = data["items"] if common pattern

# 4. Why not check len(data) >= 0 (always true)?
#    → Useless — but can add len(data) == 0 check if empty allowed

# 5. Can we combine with schema validation in this test?
#    → Possible — but keeps tests focused; separate schema test is cleaner

# 6. What if backend returns paginated {"data": [], "total": 0}?
#    → Fails on isinstance(list) — normalize in test if needed

# 7. Should we assert no null/None items in list?
#    → Good idea — add for item in data: assert item is not None

# 8. Why no check for duplicate IDs in list?
#    → Out of scope — belongs in data-quality test

# 9. Can we parametrize with expected empty vs non-empty?
#    → Overkill — current test is structural only

# 10. What if resp.json() raises JSONDecodeError?
#     → pytest fails with traceback → good; Content-Type test should catch earlier

@pytest.mark.parametrize("r", RESOURCES)
def test_list_items_are_dicts_if_present(r):
    """
    Purpose:  Ensures that when a resource list endpoint returns items, those items
              are JSON objects (dicts in Python) rather than primitives, arrays, etc.

    Why we do it this way:
    - Parametrized over RESOURCES → applies the check uniformly to every resource type
      (pets, orders, vendors, customers, events, trainers, etc.)
    - First confirms 200 OK (re-asserted for self-containment)
    - Verifies response is a list (re-asserted here too)
    - Only checks item type if list is non-empty (if data:) → safe for legitimately empty collections
    - Inspects only the first item (data[0]) → sufficient to prove structure; avoids looping over large lists
    - Clear failure message shows resource label + actual type received
    - Complements test_list_returns_list_type — together they ensure [] or [{...}, ...]

    This is a lightweight structural check — catches backend bugs like returning strings,
    numbers, or nested lists instead of resource objects.
    """
    resp = _list_all(r["base"])
    assert resp.status_code == 200, f"{r['label']} list should be 200. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert isinstance(data[0], dict), f"{r['label']} list items should be dicts, got {type(data[0])}"


# 10 follow-up questions & short answers for test_list_items_are_dicts_if_present

# 1. Why only check data[0] instead of every item in the list?
#    → Performance + sufficiency: if first is dict, backend likely returns consistent objects

# 2. What if list is empty — does the test pass?
#    → Yes — skips the dict check (if data:) → correct for empty collections

# 3. Should we fail if list contains non-dict items later in the response?
#    → Current test misses that — add for item in data: assert isinstance(item, dict) if strictness needed

# 4. Why re-assert status_code == 200 and isinstance(list)?
#    → Self-contained test — fails early with clear message even if previous tests broke

# 5. Can we add a check that each dict has at least an "id" key?
#    → Good idea — add assert "id" in data[0] (or loop) for minimal contract

# 6. What if backend returns [null, null] or [{"id":1}, "string"]?
#    → Fails on isinstance(dict) — good catch; current test would fail on first non-dict

# 7. Why not use jsonschema here for full object validation?
#    → Keep test focused on basic type — schema validation belongs in separate test (e.g. test_list_schema)

# 8. Should we parametrize expected_empty=True/False per resource?
#    → Overkill — most resources can be empty; test is structural only

# 9. What if response is huge (thousands of items) — does slicing data[0] help?
#    → Yes — avoids loading/iterating full list unnecessarily

# 10. Can we combine this with test_list_returns_list_type?
#     → Yes — merge into one test for efficiency; separate keeps failures isolated


# -----------------------------
# 2) GET BY ID 404 tests
# 7 resources * 3 invalid ids = 21 tests
# -----------------------------

@pytest.mark.parametrize("r", RESOURCES)
@pytest.mark.parametrize("item_id", INVALID_INT_IDS)
def test_get_by_id_404_for_invalid_ints(r, item_id):
    """
    Purpose:  Verifies that GET /<resource>/<invalid_integer_id> returns 404
              Not Found for a variety of invalid integer-like IDs.

    Why we do it this way:
    - Double parametrized:
      - RESOURCES → covers every resource type (pets/123, orders/-1, etc.)
      - INVALID_INT_IDS → tests multiple bad integer patterns (e.g. -1, 0, 999999999, very large positives)
    - Uses _get_by_id helper → clean, consistent, reusable
    - Focused single assertion: status_code == 404
    - Extremely detailed failure message → includes resource label, attempted ID,
      full endpoint, status, and body → instant debug when backend returns wrong code
    - Assumes INVALID_INT_IDS are chosen to never match real data (negative, huge, zero)
    - Generates 21 tests (7 resources × 3 IDs) — broad negative coverage with minimal code

    This test ensures proper "resource not found" behavior for invalid numeric IDs
    across the API — critical for REST contract and error handling.
    """
    resp = _get_by_id(r["base"], item_id)
    assert resp.status_code == 404, (
        f"Expected 404 for {r['label']} id={item_id}, got {resp.status_code}. Body: {resp.text}"
    )


# 10 follow-up questions & short answers for test_get_by_id_404_for_invalid_ints

# 1. Why separate from test_get_by_id_404 (the earlier one with TEST_IDS)?
#    → This focuses specifically on integer-like invalid IDs; earlier one may include strings/UUIDs

# 2. What values are typically in INVALID_INT_IDS?
#    → Common: [-1, 0, 999999999] or similar — non-existent, negative, overflow-risk

# 3. Should we also check the response body contains "not found" or similar?
#    → Recommended — add assert "not found" in resp.text.lower() for stronger contract

# 4. What if backend returns 400 Bad Request for negative IDs?
#    → Test fails → decide: is 400 correct for invalid format, or 404 for not found?

# 5. Why not test very large IDs (e.g. 2**63-1) for overflow?
#    → Add to INVALID_INT_IDS if backend uses signed int64 — can cause 500 or wrong lookup

# 6. Can we combine positive and negative GET-by-ID in one parametrized test?
#    → Yes — use pytest.mark.parametrize with expected_status (200 vs 404)

# 7. What if some resources allow negative IDs legitimately?
#    → Rare — mark those resources xfail or exclude from this param set

# 8. Why no Content-Type or JSON parse check on 404 response?
#    → Many APIs return text/plain or HTML on 404 — keep minimal for status-only test

# 9. Should we test malformed IDs (e.g. "abc", "1.5") in a separate test?
#    → Yes — belongs in test_get_by_id_invalid_format (expect 400 or 404)

# 10. Can we assert no side effects (e.g. no log entry created on invalid GET)?
#     → Advanced — requires server-side verification or audit log endpoint


# Non-numeric path test (one per resource) = 7 tests
@pytest.mark.parametrize("r", RESOURCES)
def test_get_by_id_404_for_non_numeric(r):
    """
    Purpose:  Verifies that attempting to GET a resource using a clearly non-numeric
              ID string returns 404 Not Found for every resource type.

    Why we do it this way:
    - Parametrized over RESOURCES → applies the check uniformly to all resource endpoints
      (pets/abc, orders/not-a-number, vendors/xyz123, etc.)
    - Uses a single fixed NON_NUMERIC_ID (presumably something like "abc", "invalid", "non-numeric")
      → focuses specifically on type/format mismatch (string on numeric-expecting route)
    - Calls _get_by_id helper → consistent with other by-ID tests (clean path construction)
    - Single focused assertion: status_code == 404
    - Detailed failure message includes resource label, attempted ID (via NON_NUMERIC_ID),
      actual status, and full response body → makes it very easy to see when backend
      returns 400, 500, 200, or anything unexpected
    - Tests a common edge case: clients sending string IDs to integer-primary-key endpoints
    - Complements test_get_by_id_404_for_invalid_ints (negative/huge ints) and earlier
      general 404 tests → together they cover numeric invalid, non-numeric, and UUID cases

    This test ensures proper type-aware "not found" or rejection behavior —
    many APIs return 400 Bad Request for format errors, but this expects 404
    (perhaps backend treats non-numeric as "does not exist").
    """
    resp = _get_by_id(r["base"], NON_NUMERIC_ID)
    assert resp.status_code == 404, (
        f"Expected 404 for {r['label']} non-numeric id, got {resp.status_code}. Body: {resp.text}"
    )


# 10 follow-up questions & short answers

# 1. What value is typically stored in NON_NUMERIC_ID?
#    → Usually a string like "abc", "invalid", "non-numeric", "hello-world" — something obviously not parsable as int

# 2. Why expect 404 instead of 400 Bad Request for non-numeric input?
#    → Depends on backend design — if it tries to parse int(id) and fails silently → 404; if validation first → 400. Test matches current expectation.

# 3. Should we test multiple non-numeric values (e.g. "abc", "1.5", "", " ")?
#    → Possible — add @pytest.mark.parametrize("non_numeric", ["abc", "1.5", "", " "]) for broader coverage

# 4. What if some resources use string/UUID primary keys — should they be excluded?
#    → Yes — if a resource accepts strings, mark it xfail or filter RESOURCES for numeric-only ones

# 5. Why not assert "invalid" or "not found" in response body?
#    → Good enhancement — add assert "not found" in resp.text.lower() or similar for stronger semantic check

# 6. Can this test fail if backend returns 422 Unprocessable Entity?
#    → Yes — common for validation libraries (Pydantic/FastAPI) on type mismatch → update to 404 or 422 depending on API

# 7. Should we check Content-Type on 404 response (e.g. application/json)?
#    → Optional — many APIs return text/plain or HTML on errors; current test ignores it for focus

# 8. Why no check for response parseability or schema on error body?
#    → Keeps test simple and focused on status code — error schema belongs in separate negative tests

# 9. What if NON_NUMERIC_ID accidentally matches a real resource name?
#    → Very unlikely with "abc"/"invalid" — but choose value far from real data; test would fail with 200

# 10. Can we merge this with test_get_by_id_404_for_invalid_ints into one test?
#     → Yes — use a single parametrized list of (id_type, expected_code) or separate for clarity

# -----------------------------
# 3) POST behavior tests
#    7 resources * 4 tests = 28 tests
# -----------------------------
@pytest.mark.parametrize("r", RESOURCES)
def test_post_creates_201(r):
    """
    Purpose:  Verifies that sending a valid creation payload to each resource's
              POST endpoint results in a successful creation response (200 or 201).

    Why we do it this way:
    - Parametrized over RESOURCES → one test definition covers creation for every
      resource type (pets, orders, inventory, vendors, customers, events, trainers, etc.)
    - Uses r["make_payload"]() → each resource provides its own factory function to
      generate a valid, unique payload (often with random names/IDs to avoid collisions)
    - Calls _create_item helper → consistent POST pattern ({base}/ + json=payload)
    - Asserts status in (200, 201) → tolerant of APIs that return either on success
      (201 Created is REST standard, but many return 200 OK)
    - Rich failure message includes resource label, actual status, and full body
      → instant visibility into 400/422 validation errors, 500s, or unexpected responses
    - No further checks here (e.g. returned ID, location header, schema) → keeps test
      focused on the minimal success contract; deeper checks belong in separate tests
      (e.g. test_create_returns_id, test_create_matches_schema)

    This is a foundational positive test — ensures the happy-path create works
    across the entire API surface with minimal duplication.
    """
    payload = r["make_payload"]()
    resp = _create_item(r["base"], payload)
    assert resp.status_code in (200, 201), (
        f"{r['label']} create should return 201/200. Got {resp.status_code}. Body: {resp.text}"
    )


# 10 follow-up questions & short answers

# 1. Why allow both 200 and 201 instead of requiring 201 Created?
#    → Many APIs (especially legacy or non-strict REST) return 200 on create — tolerant assertion avoids false failures

# 2. Why call r["make_payload"]() with no arguments?
#    → Most factories are parameterless and generate random/unique data internally (e.g. uuid-based names)

# 3. Should we assert the returned item matches the sent payload?
#    → Great next step — add resp_data = resp.json(); assert resp_data["name"] == payload["name"] etc.

# 4. What if create returns 200 but no body — is resp.json() safe?
#    → Current test doesn't call .json() — if you add it later, guard with if resp.text.strip()

# 5. Why no check for Location header with new resource URL?
#    → Optional REST best practice — add assert "Location" in resp.headers if your API supports it

# 6. Can we make this idempotent-safe (e.g. unique payload every run)?
#    → Already safe — r["make_payload"]() should generate unique data (uuid, timestamp, counter)

# 7. Should we clean up created items after the test?
#    → Usually handled by DB reset fixture or suite-level teardown — per-test delete adds overhead

# 8. What if some resources return 202 Accepted (async creation)?
#    → Test fails → update assertion to include 202 or mark those resources xfail

# 9. Why not validate the returned schema here?
#    → Keep test focused on status — schema validation belongs in separate test (e.g. test_create_schema)

# 10. Can we add a follow-up GET to confirm the item was actually created?
#     → Yes — stronger test: after create, _get_by_id(r["base"], resp.json()["id"]) → assert 200

@pytest.mark.parametrize("r", RESOURCES)
def test_post_returns_json_object(r):
    """
    Purpose:  Ensures that a successful POST to create a resource returns a JSON object
              (Python dict) in the response body, rather than a list, primitive, or empty response.

    Why we do it this way:
    - Parametrized over RESOURCES → one test definition covers the create response shape
      for every resource type (pets, orders, inventory, vendors, customers, events, trainers, etc.)
    - Uses r["make_payload"]() → generates a valid, unique payload per resource (usually with
      random/unique fields to avoid name collisions or duplicate-key errors)
    - Calls _create_item helper → consistent POST pattern and request handling
    - First confirms 200 or 201 success (standard create codes)
    - Parses JSON and checks isinstance(data, dict) → verifies the response is a single resource object
    - Clear failure message shows resource label + actual type received → makes it obvious when
      backend returns [], string, number, or malformed JSON
    - Focused structural check — does not validate content (e.g. matching payload) or full schema
      → keeps test minimal; deeper checks (schema, field equality) belong in separate tests
      (e.g. test_create_matches_schema, test_create_returns_sent_data)

    This test catches common backend bugs: returning lists on single create, empty body,
    or non-JSON success responses.
    """
    payload = r["make_payload"]()
    resp = _create_item(r["base"], payload)
    assert resp.status_code in (200, 201), f"{r['label']} create failed. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, dict), f"{r['label']} create should return dict, got {type(data)}"


# 10 follow-up questions & short answers

# 1. Why check for dict instead of requiring specific keys (e.g. "id", "name")?
#    → Keeps test focused on basic shape — key presence belongs in schema validation test

# 2. What if some resources return 201 with no body (empty dict or null)?
#    → Fails on resp.json() or isinstance(dict) — decide if empty {} is acceptable and update assertion

# 3. Should we also assert that the returned dict contains at least an "id" key?
#    → Stronger contract — add assert "id" in data and isinstance(data["id"], int)

# 4. Why re-assert status in (200, 201) here when another test already checks it?
#    → Self-contained test — fails early with create-specific message even if other tests fail

# 5. Can we compare returned fields to sent payload (e.g. name == payload["name"])?
#    → Yes — excellent follow-up: assert data.get("name") == payload["name"] for key fields

# 6. What if backend returns {"data": {...}} wrapper instead of plain object?
#    → Fails on isinstance(dict) — add normalization data = data["data"] if common pattern

# 7. Why not call jsonschema.validate here like in other tests?
#    → Keep this test purely structural (type check) — schema belongs in dedicated test

# 8. Should we handle JSONDecodeError (e.g. non-JSON body on 201)?
#    → Current code would raise → pytest shows traceback; can wrap in try/except for nicer message

# 9. What if create is async and returns 202 Accepted with {"status": "processing"}?
#    → Fails on status or dict check — update assertion to include 202 or mark xfail for those resources

# 10. Can we follow up with GET /<id> to confirm the returned ID is usable?
#     → Yes — very strong: id_ = data["id"]; get_resp = _get_by_id(r["base"], id_); assert get_resp.status_code == 200

@pytest.mark.parametrize("r", RESOURCES)
def test_post_server_generates_id_if_missing(r):
    """
    Purpose:  Verifies that when a create payload is sent **without** an "id" field,
              the server automatically generates and returns a valid integer ID
              in the response body.

    Why we do it this way:
    - Parametrized over RESOURCES → tests ID auto-generation for every resource type
      (pets, orders, inventory, vendors, customers, events, trainers, etc.) in one definition
    - Calls r["make_payload"]() → gets a valid payload, then explicitly .pop("id", None)
      → guarantees "id" is absent (even if factory sometimes includes it)
    - Uses _create_item helper → consistent POST creation pattern
    - First confirms 200/201 success (basic create health)
    - Parses JSON and checks two key properties:
      1. "id" key is present in response
      2. "id" value is an integer (common for auto-increment PKs)
    - Clear, resource-specific failure messages → show label + full response on failure
      → makes it easy to see if server returns null, string, UUID, missing key, etc.
    - Focused on the auto-generation contract — does **not** check uniqueness, monotonicity,
      or schema compliance → those belong in separate tests (e.g. test_id_uniqueness,
      test_create_schema)

    This test enforces a very common REST convention: client should not send IDs on create;
    server owns ID generation (usually auto-increment or UUID).
    """
    payload = r["make_payload"]()
    payload.pop("id", None) # ensure missing
    resp = _create_item(r["base"], payload)
    assert resp.status_code in (200, 201), f"{r['label']} create failed. Body: {resp.text}"
    data = resp.json()
    assert "id" in data, f"{r['label']} server should generate id. Response: {data}"
    assert isinstance(data["id"], int), f"{r['label']} id should be int. Got: {data['id']}"


# 10 follow-up questions & short answers

# 1. Why explicitly pop("id", None) instead of trusting make_payload() never includes it?
#    → Defensive — some factories might include placeholder ID; this guarantees absence

# 2. Should we also check that the returned ID is positive (> 0)?
#    → Yes — good addition: assert data["id"] > 0 to catch zero/negative auto-gen bugs

# 3. What if server returns string ID (e.g. UUID as str) — is int required?
#    → Depends on API — if UUIDs are used, change to isinstance(data["id"], (int, str))

# 4. Why not follow up with GET /<returned_id> to confirm it exists?
#    → Excellent stronger test — add: get_resp = _get_by_id(r["base"], data["id"]); assert get_resp.status_code == 200

# 5. Should we verify the ID is unique across multiple creates?
#    → Yes — but belongs in separate test (e.g. create twice → assert id1 != id2)

# 6. What if some resources require client-supplied ID (e.g. natural keys)?
#    → Those resources should be excluded from this test or marked xfail

# 7. Why allow 200 instead of requiring 201 Created?
#    → Many APIs return 200 on create — tolerant to avoid false failures

# 8. Can we assert no "id" in payload was honored (i.e. different ID returned)?
#    → Possible — if factory includes id, compare payload["id"] != data["id"]

# 9. What if response is {"data": {"id": 123}} wrapper — does test fail?
#    → Yes — add normalization data = data.get("data", data) if wrapper is common

# 10. Should we check ID monotonicity (new ID > previous ID)?
#     → Advanced — requires multiple creates in same test or separate monotonic test

@pytest.mark.parametrize("r", RESOURCES)
def test_post_rejects_non_int_id_400(r):
    """
    Purpose:  Verifies that sending a create payload with an "id" field set to a
              non-integer value (e.g. string) is rejected by the server with HTTP 400
              Bad Request for every resource type.

    Why we do it this way:
    - Parametrized over RESOURCES → tests input validation uniformly across all
      resource creation endpoints (pets, orders, inventory, vendors, customers, events, trainers, etc.)
    - Starts with a valid payload from r["make_payload"]() → ensures base data is correct
    - Explicitly sets payload["id"] = "not-an-int" → forces a type mismatch (string instead of int)
    - Uses _create_item helper → consistent POST pattern for creation
    - Single focused assertion: status_code == 400 → checks proper rejection on invalid input
    - Detailed failure message includes resource label, actual status, and full response body
      → makes it easy to diagnose when backend returns 201 (ignores invalid ID), 500 (crash), 422, etc.
    - Tests a critical validation rule: if server auto-generates IDs (common REST pattern),
      it should reject client-supplied invalid IDs rather than silently ignoring or crashing
    - Complements test_post_server_generates_id_if_missing → together they enforce "server owns ID"

    This negative test catches weak validation or silent ID override bugs early.
    """
    payload = r["make_payload"]()
    payload["id"] = "not-an-int"
    resp = _create_item(r["base"], payload)
    assert resp.status_code == 400, (
        f"{r['label']} should reject non-int id with 400. Got {resp.status_code}. Body: {resp.text}"
    )


# 10 follow-up questions & short answers

# 1. Why specifically "not-an-int" as the bad value instead of e.g. 3.14 or None?
#    → String is clearest type mismatch; backend likely tries int(id) and fails → 400

# 2. Should we test other invalid types (None, float, bool, list, dict)?
#    → Yes — great expansion: parametrize bad_id = [None, 3.14, True, [], {}] and expect 400

# 3. What if some resources allow string IDs (e.g. UUID or slug)?
#    → Those should be excluded from RESOURCES or marked xfail for this test

# 4. Why expect 400 instead of 422 Unprocessable Entity?
#    → Depends on API convention — 400 common for bad input; update to 400/422 if backend uses 422

# 5. Should we check the error message contains "id must be integer" or similar?
#    → Stronger test — add assert "id" in resp.text.lower() and "integer" in resp.text.lower()

# 6. What if server silently ignores the invalid "id" and creates anyway?
#    → Test fails (gets 200/201) → good catch; proves server does not honor bad ID

# 7. Why not also test very large int IDs (overflow) in a separate case?
#    → Good idea — separate test for int overflow (e.g. payload["id"] = 2**1000)

# 8. Can we assert that the returned body includes validation details (Pydantic style)?
#    → Yes — if backend uses FastAPI/Pydantic, assert "detail" in resp.json() and "id" in detail

# 9. What if create succeeds with the string ID (coerces it)?
#    → Test fails → decide if coercion is acceptable; usually not for strict typing

# 10. Should we follow up with GET /<sent_id> to confirm string ID was rejected?
#     → Possible — but unnecessary; 400 already means rejection; GET would be 404 or 400

# -----------------------------
# 4) Duplicate ID tests
#    7 resources * 1 test = 7 tests
# -----------------------------
@pytest.mark.parametrize("r", RESOURCES)
def test_post_duplicate_id_409(r):
    """
    Verify:
      1. First POST with explicit ID succeeds
      2. Second POST with same ID returns 409
    Uses a guaranteed-unique ID so it never collides with previous test data.
    """

    # Generate a unique integer ID per test run
    # uuid4 ensures it will never collide
    unique_id = uuid.uuid4().int % 10_000_000_000  # large positive int

    # ---- Create first item with explicit id ----
    payload1 = r["make_payload"]()
    payload1["id"] = unique_id

    resp1 = _create_item(r["base"], payload1)

    assert resp1.status_code in (200, 201), (
        f"{r['label']} create #1 failed. "
        f"Status: {resp1.status_code}. Body: {resp1.text}"
    )

    # ---- Create second item with same id (should fail) ----
    payload2 = r["make_payload"]()
    payload2["id"] = unique_id

    resp2 = _create_item(r["base"], payload2)

    assert resp2.status_code == 409, (
        f"{r['label']} duplicate id should 409. "
        f"Got {resp2.status_code}. Body: {resp2.text}"
    )



# ----------------------------
# Config: point this at your running API
# ----------------------------


# IMPORTANT:
# These "base" paths must match your Namespace prefixes.
# If your namespaces are mounted differently, update these.
RESOURCES = [
    {
        "label": "Pet",
        "base": "/pet",
        "searchable_fields": ["name", "type", "status"],
        "filterable_fields": ["name", "type", "status", "order_id"],
        "make_payload": lambda i: {
            "name": f"Pet {i}",
            "type": "dog",
            "status": "available",
            "order_id": 0,
        },
        "filter_key": "status",
        "filter_val": "available",
        "search_key": "name",
    },
    {
        "label": "Customer",
        "base": "/customer",
        "searchable_fields": ["name", "email", "date"],
        "filterable_fields": ["name", "email", "date", "purchase"],
        "make_payload": lambda i: {
            "name": f"Customer {i}",
            "date": "2026-02-13",
            "purchase": 1,
            "email": f"customer{i}@example.com",
        },
        "filter_key": "purchase",
        "filter_val": 1,
        "search_key": "email",
    },
    {
        "label": "Inventory",
        "base": "/inventory",
        "searchable_fields": ["pet_id"],
        "filterable_fields": ["pet_id", "inventory"],
        "make_payload": lambda i: {
            "inventory": 10,
            "pet_id": i,
        },
        "filter_key": "inventory",
        "filter_val": 10,
        "search_key": "pet_id",
    },
    {
        "label": "Vet",
        "base": "/vet",
        "searchable_fields": ["name", "contact_form"],
        "filterable_fields": ["name", "contact_form", "contact_info"],
        "make_payload": lambda i: {
            "name": f"Vet {i}",
            "contact_form": "email",
            "contact_info": 123456,
        },
        "filter_key": "contact_form",
        "filter_val": "email",
        "search_key": "name",
    },
    {
        "label": "Trainer",
        "base": "/trainer",
        "searchable_fields": ["name", "contact_form"],
        "filterable_fields": ["name", "contact_form", "contact_info"],
        "make_payload": lambda i: {
            "name": f"Trainer {i}",
            "contact_form": "phone",
            "contact_info": 987654,
        },
        "filter_key": "contact_form",
        "filter_val": "phone",
        "search_key": "name",
    },
    {
        "label": "Vendor",
        "base": "/vendor",
        "searchable_fields": ["name", "contact_form", "point_of_contact", "contact_info"],
        "filterable_fields": ["name", "contact_form", "point_of_contact", "product"],
        "make_payload": lambda i: {
            "name": f"Vendor {i}",
            "contact_form": "email",
            "contact_info": "vendor@example.com",
            "point_of_contact": "Alice",
            "product": 1,
        },
        "filter_key": "product",
        "filter_val": 1,
        "search_key": "point_of_contact",
    },
    {
        "label": "Event",
        "base": "/event",
        "searchable_fields": ["name", "date"],
        "filterable_fields": ["name", "date", "location"],
        "make_payload": lambda i: {
            "name": f"Event {i}",
            "date": "2026-02-13",
            "location": 100,
        },
        "filter_key": "location",
        "filter_val": 100,
        "search_key": "name",
    },
]

# ----------------------------
# Swagger discovery
# ----------------------------
def _load_swagger() -> Dict[str, Any]:
    """
    Purpose: Attempts to fetch the OpenAPI/Swagger JSON document from one of several
             common locations on the local API server. Returns the parsed dict on success.

    Why we do it this way:
    - Many FastAPI/Flask/Connexion apps expose Swagger at slightly different paths.
      Trying multiple common ones avoids hardcoding a single fragile path.
    - Used during test setup / discovery phase to dynamically understand the API
      (endpoints, schemas, resources) without manual configuration.
    - Raises clear AssertionError with actionable advice if none of the paths work.
    - Switching to make_request adds:
      - automatic retries (helpful when dev server is slow to start or flaky)
      - consistent 10-second timeout per attempt
      - verify=False (useful for local self-signed certs or plain HTTP)
      - retry logging to console
      - eventual Tkinter popup if the server is completely unreachable after retries
    - Explicit assert r is not None protects against total network failure
      (all retries exhausted) — prevents cryptic AttributeError later.
    - Loops through likely paths in order of most common first → usually finds it quickly

    Returns: parsed OpenAPI JSON as dict
    Raises: AssertionError if no valid swagger.json is found at any tried path
            or if network completely fails
    """
    # Try common swagger.json locations
    for p in ("/swagger.json", "/api/swagger.json", "/v1/swagger.json", "/api/v1/swagger.json"):
        r = make_request("GET", p)

        # Optional: protect against total network failure (all retries failed)
        assert r is not None, (
            f"make_request completely failed (no response) when trying {p}\n"
            "Check if the API server is running at http://127.0.0.1:5001"
        )

        if r.status_code == 200:
            return r.json()

    raise AssertionError(
        "Could not find swagger.json at common paths. "
        "Try opening /swagger.json in browser to see where it is."
    )


# 10 follow-up questions & short answers

# 1. Why try multiple paths instead of hardcoding one (e.g. /openapi.json)?
#    → FastAPI defaults to /openapi.json but many apps use /swagger.json or /api/swagger.json — trying several makes discovery robust

# 2. Should we add more paths like "/openapi.json", "/docs/openapi.json", "/spec"?
#    → Yes — very common in newer FastAPI versions; add them to the tuple for better coverage

# 3. Why raise AssertionError instead of returning None or raising custom exception?
#    → This is a test-setup helper — AssertionError fails the entire test suite early with clear message

# 4. What if the server requires authentication to access swagger.json?
#    → Current code assumes public access — add headers= with token if needed (or use a fixture)

# 5. Why no caching of the loaded swagger dict (e.g. module-level global)?
#    → Safe for most cases, but can add @lru_cache or global var if fetched repeatedly in same run

# 6. Should we validate that the returned dict has "openapi" key or "paths"?
#    → Good idea — add basic check: assert "openapi" in swagger or "paths" in swagger after return

# 7. What if server returns 200 but invalid JSON (malformed)?
#    → r.json() raises JSONDecodeError → test crashes with traceback; can wrap in try/except for nicer message

# 8. Why use make_request instead of httpx directly here?
#    → Consistency with rest of suite (retries, timeout, verify=False, logging, Tkinter popup on failure)

# 9. Can we log which path succeeded (e.g. print("Loaded from", p))?
#    → Useful for debugging — add print(f"Swagger loaded from {p}") before return

# 10. What happens if multiple paths return 200 — does it take the first one?
#     → Yes — order matters; common paths first → usually correct one; rare to have multiple valid ones

def _discover_bases(swagger: Dict[str, Any]) -> List[str]:
    """
    Purpose:  Scans the loaded OpenAPI/Swagger document to discover all resource base paths
              that appear to support the "common extras" endpoints (specifically by looking
              for paths that end with /count).

    Why we do it this way:
    - Uses the /count endpoint as a reliable marker because it is one of the most consistent
      "extra" endpoints added to resources via register_common_extras (others like /ids, /exists,
      /search, /filter, /bulk/* are optional or vary).
    - Extracts the base path by slicing off the "/count" suffix → simple string operation
      that works for both /pets/count → /pets and /inventory/count → /inventory
    - Collects unique bases in a set → automatically deduplicates and avoids duplicates
    - Returns sorted(list) → deterministic order (alphabetical) makes test output stable
      and easier to read/debug
    - Operates purely on the swagger dict → no network calls, fast, repeatable
    - Feeds into dynamic test generation (e.g. _build_cases, parametrized tests) →
      enables auto-discovery of testable resources without hardcoding paths
    - Assumes convention: if a resource has /count, it likely has the full suite of extras

    Returns: sorted list of discovered base paths (e.g. ["/pets", "/orders", "/inventory"])
    """
    paths = swagger.get("paths", {})
    bases = set()
    for path in paths.keys():
        # Example: /pet/count -> base /pet
        if path.endswith("/count"):
            base = path[: -len("/count")]
            bases.add(base)
    return sorted(bases)


# 10 follow-up questions & short answers

# 1. Why use /count specifically as the marker instead of /exists or /ids?
#    → /count is the most consistently implemented extra endpoint across resources — least likely to be missing

# 2. What if a resource has /something/count but it's not a base resource?
#    → Rare edge case — would incorrectly include /something as base; can refine with starts_with("/") or len(split("/")) check

# 3. Why use set() + sorted() instead of list and append if not in list?
#    → set() is faster for deduplication + sorted() gives stable, readable output order

# 4. Should we also check for other extras (e.g. require both /count and /ids)?
#    → Possible — but would exclude resources missing one extra; current approach is more inclusive

# 5. What if path is /v1/pets/count — does base become /v1/pets correctly?
#    → Yes — slicing removes only the suffix; preserves prefix/version

# 6. Why not use swagger["paths"][path]["get"] to confirm it's a real endpoint?
#    → Overkill for discovery — existence of path key is enough signal in most OpenAPI docs

# 7. Can we add a minimum length check (e.g. base != "" and len(base.split("/")) > 1)?
#    → Good idea — prevents junk like "/" or "/count" being added as base

# 8. What happens if no /count paths exist at all?
#    → Returns empty list → downstream tests either skip or fail gracefully (depending on usage)

# 9. Should we log discovered bases (print or logging.debug)?
#    → Helpful for debugging — add print(f"Discovered bases: {bases}") after loop

# 10. Why not return a list of dicts with more info (e.g. label, has_bulk, etc.)?
#     → Keep simple — this function only discovers bases; richer mapping happens later (e.g. in RESOURCES construction)

def _pick_create_path(swagger: Dict[str, Any], base: str) -> str:
    """
    Purpose:  Determines the correct POST endpoint path for creating a new resource
              under a given base path by inspecting the OpenAPI/Swagger document.

    Why we do it this way:
    - OpenAPI specs are inconsistent across projects: some servers define POST at
      exactly /{base} (e.g. POST /pets), others at /{base}/ (POST /pets/).
      Hardcoding one or the other would break half the time.
    - Checks both variants explicitly against the "paths" dictionary:
      1. First tries exact base (e.g. "/pets")
      2. Then tries base + trailing slash ("/pets/")
    - Returns the first matching path that has a "post" operation defined
    - Falls back to base + "/" if neither is found → safe default (most servers
      accept both forms due to URL normalization, but we prefer the one declared)
    - Relies solely on swagger dict → fast, no extra network calls, deterministic
    - Used during dynamic test setup to ensure _create_item sends POST to a path
      the backend actually recognizes → prevents false 404/405 failures in create tests

    Returns: the preferred create path (e.g. "/pets" or "/pets/")
    """
    paths = swagger.get("paths", {})
    if base in paths and "post" in paths[base]:
        return base
    if f"{base}/" in paths and "post" in paths[f"{base}/"]:
        return f"{base}/"
    # fallback to base + "/"
    return f"{base}/"


# 10 follow-up questions & short answers

# 1. Why prefer the exact base path over base + "/" when both exist?
#    → The code checks exact base first → follows OpenAPI declaration order; exact match is usually the canonical form

# 2. What if neither path has a "post" method — why return base + "/" anyway?
#    → Defensive fallback — most servers normalize trailing slash; better to try something than fail early

# 3. Should we raise an error if no POST is found at either path?
#    → Possible — add assert "post" in paths.get(base, {}) or paths.get(f"{base}/", {}) for stricter discovery

# 4. Why not check for other create indicators (tags, summary="Create", operationId)?
#    → Simpler and faster to just look for "post" key — sufficient signal in 99% of OpenAPI docs

# 5. What if base is already "/pets/" (trailing slash from discovery)?
#    → Code still works — f"{base}/" becomes "/pets//" but most servers normalize it; can rstrip("/") first if paranoid

# 6. Can we log which path was chosen (e.g. print("Using create path:", path))?
#    → Very useful for debugging — add print(f"Selected create path for {base}: {returned_path}")

# 7. Should we verify the POST has requestBody with JSON content?
#    → Stronger — but overkill for this helper; belongs in deeper schema validation

# 8. What if the spec uses /v1/pets vs /pets — does base include version?
#    → Yes — discovery usually includes version prefix; function handles both correctly

# 9. Why return str instead of raising ValueError on no match?
#    → Graceful degradation — lets tests run and fail later on 405/404 with real endpoint feedback

# 10. Can we cache the result per base (e.g. @lru_cache)?
#     → Yes — safe since swagger dict is static per test run; speeds up repeated calls in large suites


# ----------------------------
# Generic payload maker (minimal valid objects)
# You can override per base if needed.
# ----------------------------
def _default_payload_for_base(base: str, i: int) -> Dict[str, Any]:
    """
    Purpose:  Generates a minimal, valid default payload suitable for creating
              a new resource of the given base path type, using a simple heuristic
              based on the base path name.

    Why we do it this way:
    - Many tests need to create resources quickly without caring about specific
      field values — this function provides "good enough" defaults so tests can
      focus on behavior (create, list, get, update, delete) rather than payload crafting.
    - Uses string matching on base.lower() → simple, fast, no dependency on swagger
      or external config; works even if OpenAPI discovery fails or is partial.
    - Hardcodes minimal required fields per resource type (name, type/status, contact, etc.)
      → enough to pass basic validation and creation without triggering 400/422 errors.
    - Includes incremental counter i → produces unique-ish names/emails (Pet 1, Customer 42…)
      → reduces accidental collisions when running many creates in sequence.
    - Returns a fallback {"name": f"Item {i}"} when base doesn't match known patterns
      → graceful degradation; allows tests to run (and fail informatively) on unknown resources.
    - Keeps payloads extremely simple → easy to override in specific tests when more fields
      are needed (e.g. photos, dates, nested objects).
    - Used heavily in dynamic test generation (e.g. test_post_creates_201, bulk creates,
      search/filter seeding) → centralizes default data creation logic.

    Returns: a dict payload that should be acceptable for POST /{base}/
    """
    # Heuristics based on base name
    b = base.lower()
    if "pet" in b:
        return {"name": f"Pet {i}", "type": "dog", "status": "available", "order_id": 0}
    if "customer" in b:
        return {"name": f"Customer {i}", "date": "2026-02-13", "purchase": 1, "email": f"c{i}@example.com"}
    if "inventory" in b:
        return {"inventory": 10, "pet_id": i}
    if "vet" in b:
        return {"name": f"Vet {i}", "contact_form": "email", "contact_info": 123456}
    if "trainer" in b:
        return {"name": f"Trainer {i}", "contact_form": "phone", "contact_info": 987654}
    if "vendor" in b:
        return {
            "name": f"Vendor {i}",
            "contact_form": "email",
            "contact_info": "vendor@example.com",
            "point_of_contact": "Alice",
            "product": 1,
        }
    if "event" in b:
        return {"name": f"Event {i}", "date": "2026-02-13", "location": 100}
    # fallback: try name-only
    return {"name": f"Item {i}"}


# 10 follow-up questions & short answers

# 1. Why use simple string "in b" matching instead of exact equality or regex?
#    → Flexible — matches /pets, /v1/pets, /pet-store/pets, /pets-v2 etc. without needing full path parsing

# 2. What happens when a new resource type is added (e.g. "appointment")?
#    → Falls back to {"name": f"Item {i}"} → tests still run but may fail on 400 if more fields required

# 3. Should we raise an error instead of returning fallback for unknown bases?
#    → Possible — add raise ValueError(f"No default payload defined for base: {base}") for stricter discovery

# 4. Why hardcode "dog" and "available" for pets — why not "cat" or "sold"?
#    → Minimal valid values that pass most pet creation rules; tests can override when specific status needed

# 5. Why use fixed dates like "2026-02-13" instead of datetime.now()?
#    → Deterministic — makes test output reproducible; avoids timezone or format issues

# 6. Is it safe to reuse the same payload structure for every test run?
#    → Yes — i increments per call → names/emails stay unique within a test session

# 7. Should we make payloads more complete (add required fields from swagger)?
#    → Possible — but increases maintenance; current minimal approach is easier to evolve

# 8. What if a resource requires nested objects or arrays (e.g. pet photos)?
#    → Current defaults will likely 400 — override in specific tests or extend function with more cases

# 9. Can we add type hints or validation to ensure returned dict matches expected schema?
#    → Overkill for helper — schema validation belongs in the tests that use the payload

# 10. Why not use a dict mapping {base_pattern: payload_factory} instead of if-chain?
#     → if-chain is simpler for small number of cases; dict + lambda would work too but more verbose

# ----------------------------
# Test resource wrapper discovered from swagger
# ----------------------------def _make_resource(swagger: Dict[str, Any], base: str) -> Dict[str, Any]:
    """
    Purpose:  Builds a complete resource configuration dictionary for a given base path,
              using information from the OpenAPI/Swagger document and heuristic defaults.

    Why we do it this way:
    - Centralizes all metadata needed for dynamic testing of a resource (create path,
      label, payload factory, search/filter keys & values) in one place.
    - Called once per discovered base during setup → produces RESOURCE-like dicts
      that parametrized tests can consume directly (test_post_creates_201, test_list_items_match_schema, etc.)
    - Uses _pick_create_path → ensures correct POST endpoint (with or without trailing /)
    - Derives human-readable label from base path (e.g. "/pets" → "Pets", "/v1/customers" → "Customers")
    - Chooses sensible search_key and filter_key + example filter_val based on base name heuristics
      → enables search/filter tests to work out-of-the-box without manual config per resource
    - Hardcodes per-resource defaults for filter_key/val → matches common fields (status for pets,
      purchase for customers, inventory for stock, etc.) so seeding and matching work reliably
    - Provides lambda i: _default_payload_for_base(base, i) → lazy, incremental payload generation
      with unique values → safe for repeated creates in same test session
    - Returns a dict with all keys expected by tests → makes dynamic test generation simple
      and extensible (add new keys like "has_bulk" or "id_type" later without breaking old tests)

    Returns: dict with keys: label, base, create, make_payload, filter_key, filter_val, search_key
    """
    create_path = _pick_create_path(swagger, base)
    # best-effort label
    label = base.strip("/").split("/")[-1].title()
    # choose a search key & filter key based on likely fields
    # these will be used only if endpoints exist
    search_key = "name"
    filter_key = "name"
    filter_val = None
    bl = base.lower()
    if "pet" in bl:
        filter_key, filter_val = "status", "available"
        search_key = "name"
    elif "customer" in bl:
        filter_key, filter_val = "purchase", 1
        search_key = "email"
    elif "inventory" in bl:
        filter_key, filter_val = "inventory", 10
        search_key = "pet_id"
    elif "vet" in bl:
        filter_key, filter_val = "contact_form", "email"
        search_key = "name"
    elif "trainer" in bl:
        filter_key, filter_val = "contact_form", "phone"
        search_key = "name"
    elif "vendor" in bl:
        filter_key, filter_val = "product", 1
        search_key = "point_of_contact"
    elif "event" in bl:
        filter_key, filter_val = "location", 100
        search_key = "name"
    return {
        "label": label,
        "base": base,
        "create": create_path,
        "make_payload": lambda i: _default_payload_for_base(base, i),
        "filter_key": filter_key,
        "filter_val": filter_val,
        "search_key": search_key,
    }


# 10 follow-up questions & short answers

# 1. Why derive label from base path instead of using swagger tags or summary?
#    → Simple and reliable — swagger tags can be missing or inconsistent; path is always present

# 2. What if a resource has multiple possible search/filter keys — why pick one?
#    → Keep config minimal — tests use one key; can extend dict later with list of options

# 3. Why hardcode filter_val (e.g. "available", 1, 10) instead of dynamic values?
#    → Deterministic seeding — tests can reliably create/match items with known values

# 4. Should we validate these keys actually exist in the schema (from swagger)?
#    → Possible — but adds complexity; current heuristic works well enough for most APIs

# 5. What if make_payload lambda fails for unknown base (fallback {"name": …})?
#    → Tests may 400 on create — clear failure; add raise ValueError for stricter behavior

# 6. Why use lambda i: … instead of a pre-bound function?
#    → Lazy evaluation — i is passed at call time; avoids capturing i from outer scope

# 7. Can we add more metadata (e.g. "id_type": "int", "has_bulk": True)?
#    → Yes — easy extension; just add keys to the returned dict when needed by tests

# 8. What if base has version prefix (/v1/pets) — does label become "Pets" correctly?
#    → Yes — split("/")[-1] takes last segment; .title() capitalizes nicely

# 9. Should we check swagger for actual POST requestBody schema to generate better defaults?
#    → Ideal but complex — would require parsing schemas; current simple approach scales better

# 10. Why set filter_val = None initially instead of a default like "name"?
#     → Prevents false positives — tests skip filter if val=None (see test cases)


def _make_resource(swagger: Dict[str, Any], base: str) -> Dict[str, Any]:
    """
    Purpose:  Builds a complete resource configuration dictionary for a given base path,
              using information from the OpenAPI/Swagger document and heuristic defaults.

    Why we do it this way:
    - Centralizes all metadata needed for dynamic testing of a resource (create path,
      label, payload factory, search/filter keys & values) in one place.
    - Called once per discovered base during setup → produces RESOURCE-like dicts
      that parametrized tests can consume directly (test_post_creates_201, test_list_items_match_schema, etc.)
    - Uses _pick_create_path → ensures correct POST endpoint (with or without trailing /)
    - Derives human-readable label from base path (e.g. "/pets" → "Pets", "/v1/customers" → "Customers")
    - Chooses sensible search_key and filter_key + example filter_val based on base name heuristics
      → enables search/filter tests to work out-of-the-box without manual config per resource
    - Hardcodes per-resource defaults for filter_key/val → matches common fields (status for pets,
      purchase for customers, inventory for stock, etc.) so seeding and matching work reliably
    - Provides lambda i: _default_payload_for_base(base, i) → lazy, incremental payload generation
      with unique values → safe for repeated creates in same test session
    - Returns a dict with all keys expected by tests → makes dynamic test generation simple
      and extensible (add new keys like "has_bulk" or "id_type" later without breaking old tests)

    Returns: dict with keys: label, base, create, make_payload, filter_key, filter_val, search_key
    """
    create_path = _pick_create_path(swagger, base)
    # best-effort label
    label = base.strip("/").split("/")[-1].title()
    # choose a search key & filter key based on likely fields
    # these will be used only if endpoints exist
    search_key = "name"
    filter_key = "name"
    filter_val = None
    bl = base.lower()
    if "pet" in bl:
        filter_key, filter_val = "status", "available"
        search_key = "name"
    elif "customer" in bl:
        filter_key, filter_val = "purchase", 1
        search_key = "email"
    elif "inventory" in bl:
        filter_key, filter_val = "inventory", 10
        search_key = "pet_id"
    elif "vet" in bl:
        filter_key, filter_val = "contact_form", "email"
        search_key = "name"
    elif "trainer" in bl:
        filter_key, filter_val = "contact_form", "phone"
        search_key = "name"
    elif "vendor" in bl:
        filter_key, filter_val = "product", 1
        search_key = "point_of_contact"
    elif "event" in bl:
        filter_key, filter_val = "location", 100
        search_key = "name"
    return {
        "label": label,
        "base": base,
        "create": create_path,
        "make_payload": lambda i: _default_payload_for_base(base, i),
        "filter_key": filter_key,
        "filter_val": filter_val,
        "search_key": search_key,
    }


# 10 follow-up questions & short answers

# 1. Why derive label from base path instead of using swagger tags or summary?
#    → Simple and reliable — swagger tags can be missing or inconsistent; path is always present

# 2. What if a resource has multiple possible search/filter keys — why pick one?
#    → Keep config minimal — tests use one key; can extend dict later with list of options

# 3. Why hardcode filter_val (e.g. "available", 1, 10) instead of dynamic values?
#    → Deterministic seeding — tests can reliably create/match items with known values

# 4. Should we validate these keys actually exist in the schema (from swagger)?
#    → Possible — but adds complexity; current heuristic works well enough for most APIs

# 5. What if make_payload lambda fails for unknown base (fallback {"name": …})?
#    → Tests may 400 on create — clear failure; add raise ValueError for stricter behavior

# 6. Why use lambda i: … instead of a pre-bound function?
#    → Lazy evaluation — i is passed at call time; avoids capturing i from outer scope

# 7. Can we add more metadata (e.g. "id_type": "int", "has_bulk": True)?
#    → Yes — easy extension; just add keys to the returned dict when needed by tests

# 8. What if base has version prefix (/v1/pets) — does label become "Pets" correctly?
#    → Yes — split("/")[-1] takes last segment; .title() capitalizes nicely

# 9. Should we check swagger for actual POST requestBody schema to generate better defaults?
#    → Ideal but complex — would require parsing schemas; current simple approach scales better

# 10. Why set filter_val = None initially instead of a default like "name"?
#     → Prevents false positives — tests skip filter if val=None (see test cases)

# ----------------------------
# Shared helpers for the tests
# ----------------------------
def _create_one(r: Dict[str, Any], *, i: int) -> Dict[str, Any]:
    """
    Purpose: Creates one resource of a given type using the configuration in dict 'r'
             and returns the created object (with id).

    Why we do it this way:
    - 'r' is a reusable config dict → allows the same logic to create pets, inventory items,
      orders, vendors, customers, events, trainers, etc. without duplicating code.
    - Uses r["make_payload"](i) → generates a valid, unique payload for each call (i ensures
      incremental uniqueness, e.g. different names/emails)
    - Uses make_request("POST", ...) → leverages the robust httpx client with retries,
      timeout, verify=False, logging, and Tkinter popup on total failure
    - Explicitly checks resp is not None → protects against complete network failure
      (all retries exhausted) — prevents cryptic AttributeError later
    - Asserts 200/201 success → tolerant of APIs that return either code on create
    - Parses JSON and enforces "id" exists and is integer → core contract for most resources
    - Raises detailed AssertionError messages with label, endpoint, status, payload,
      and truncated body → makes failures extremely actionable in pytest output
    - Returns only the parsed data dict → matches what most tests need (the created object)

    This is the central "create resource" primitive used by almost all positive create
    tests, bulk creates, search/filter seeding, and lifecycle tests.
    """
    payload = r["make_payload"](i)
    resp = make_request(
        method="POST",
        url=r["create"],           # e.g. "/pets/", "/inventory/", "/store/order", etc.
        json=payload
    )
    assert resp is not None, (
        f"{r['label']} create completely failed — no response object after retries.\n"
        f"POST {r['create']}\n"
        f"payload={payload}"
    )
    assert resp.status_code in (200, 201), (
        f"{r['label']} create failed.\n"
        f"POST {r['create']}\n"
        f"status={resp.status_code}\n"
        f"body={resp.text[:1000]}"
    )
    data = resp.json()
    assert isinstance(data.get("id"), int), (
        f"{r['label']} create missing/invalid id.\n"
        f"Body: {data}"
    )
    return data


# 10 follow-up questions & short answers

# 1. Why assert isinstance(data.get("id"), int) instead of data["id"]?
#    → Safer — uses .get() to avoid KeyError if "id" missing; test fails on type anyway

# 2. Should we also check id > 0 (positive integer)?
#    → Yes — good addition: assert data["id"] > 0 to catch zero/negative auto-gen bugs

# 3. What if some resources return string IDs (UUIDs) — does test fail?
#    → Yes — change to isinstance(data.get("id"), (int, str)) or make per-resource configurable

# 4. Why truncate body to [:1000] in error message?
#    → Prevents pytest output from exploding with huge HTML error pages or logs

# 5. Should we follow up with GET /<id> to confirm creation?
#    → Stronger test — add: get_resp = _get_by_id(r["base"], data["id"]); assert get_resp.status_code == 200

# 6. What if create returns 201 with no body or empty dict?
#    → Fails on resp.json() or "id" missing — decide if empty success is allowed

# 7. Can we add schema validation (jsonschema.validate) right here?
#    → Possible — but keeps helper focused on creation; schema check belongs in separate test

# 8. Why no cleanup (DELETE the created item) after return?
#    → Usually handled by DB reset fixture or suite teardown — per-call delete adds overhead

# 9. What if r["create"] is wrong (wrong path) — how to debug?
#    → Failure message shows exact POST path + payload + body → very clear when 404/405 occurs

# 10. Should we return (resp, data) instead of just data?
#     → Current return is simple and matches most usage; can change if tests need headers/status often

def _bulk_create(r: Dict[str, Any], objs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Purpose:  Sends a bulk creation request to the /{base}/bulk endpoint
              with a list of objects to create in one HTTP call, then returns
              the server's metadata response.

    Why we do it this way:
    - Bulk operations reduce the number of round-trips → much faster for seeding
      test data, stress/performance tests, or creating dozens/hundreds of items
      in setup or parametrized cases.
    - The response is expected to contain metadata ("created": list of created items,
      "count": int) rather than repeating the full objects → typical pattern for
      efficient bulk endpoints (avoids large response bodies).
    - Uses make_request("POST", ...) → leverages the robust httpx client with:
      - automatic retries on transient network issues (common on local dev servers)
      - consistent 10-second timeout per attempt
      - verify=False (handles local self-signed certs or plain HTTP)
      - retry logging to console
      - eventual Tkinter popup if the server is completely unreachable after retries
    - Explicit assert resp is not None → protects against total network failure
      (all retries exhausted) — prevents cryptic AttributeError later
    - Asserts 200/201 success → tolerant of APIs that return either on bulk create
    - Checks for expected response keys ("created" and "count") → enforces the
      bulk metadata contract
    - Returns only the parsed metadata dict → matches what most tests need
      (count verification, sometimes iterating created IDs); full objects rarely needed

    This helper is used in bulk_create tests, seeding for search/filter, and
    performance/stress scenarios where creating many items sequentially would be too slow.
    """
    resp = make_request(
        method="POST",
        url=f"{r['base']}/bulk",
        json=objs
    )
    assert resp is not None, (
        f"{r['label']} bulk create completely failed — no response after retries.\n"
        f"POST {r['base']}/bulk\n"
        f"payload size={len(objs)} items"
    )
    assert resp.status_code in (200, 201), (
        f"{r['label']} bulk create failed.\n"
        f"POST {r['base']}/bulk\n"
        f"status={resp.status_code}\n"
        f"body={resp.text[:1000]}"
    )
    data = resp.json()
    assert "created" in data and "count" in data, (
        f"{r['label']} bulk create response missing expected keys.\n"
        f"Got: {data}"
    )
    return data


# 10 follow-up questions & short answers

# 1. Why expect "created" to be a list and "count" an int — why not check types?
#    → Keeps helper minimal; type checks belong in specific tests (e.g. assert isinstance(data["count"], int))

# 2. Should we add assert data["count"] == len(objs) for full success?
#    → Yes — very strong: add assert data["count"] == len(objs), "Partial bulk create"

# 3. What if server returns full created objects in "created" — do we care?
#    → Current code ignores contents — can iterate data["created"] for deeper validation if needed

# 4. Why allow 200 or 201 instead of requiring 201 Created?
#    → Many bulk endpoints return 200 OK — tolerant to avoid false failures

# 5. What if bulk create partially succeeds (count < len(objs))?
#    → Test passes unless you add the stricter count == len(objs) assertion

# 6. Should we check that len(data["created"]) matches count?
#    → Good idea — add assert len(data["created"]) == data["count"] for consistency

# 7. Why truncate body to [:1000] in error message?
#    → Prevents pytest output from becoming unreadable with huge error pages or logs

# 8. Can we add retry on 5xx server errors (not just network failures)?
#    → Possible — extend make_request to retry on certain status codes if backend is flaky

# 9. What if objs is empty list — should we allow or reject?
#    → Current code sends [] → backend may 400 or 200 with count=0; test can decide

# 10. Should we return data["created"] list instead of metadata dict?
#     → No — metadata is usually what bulk tests need; can return (data, data["created"]) if desired

def _bulk_delete(r: Dict[str, Any], ids: List[int]) -> Dict[str, Any]:
    """
    Purpose:  Sends a bulk deletion request by POSTing a list of IDs
              to the /{base}/bulk/delete endpoint, then returns the
              server's metadata response about what was actually deleted.

    Why we do it this way:
    - Bulk delete is more efficient than individual DELETE calls (fewer requests,
      often better transaction handling on the server side, especially with DB atomicity).
    - Uses POST instead of DELETE with body → common safe pattern (some proxies/firewalls
      block DELETE with body; POST is universally allowed).
    - Payload is simple {"ids": [int, int, ...]} → easy to serialize, clear contract.
    - Response expected to report "deleted" (actual count successfully removed)
      and "requested" (number of IDs sent) — allows verification of full/partial success.
    - Uses make_request("POST", ...) → leverages the robust httpx client with:
      - automatic retries on transient network issues (common on local dev servers)
      - consistent 10-second timeout per attempt
      - verify=False (handles local self-signed certs or plain HTTP)
      - retry logging to console
      - eventual Tkinter popup if the server is completely unreachable after retries
    - Explicit assert resp is not None → protects against total network failure
      (all retries exhausted) — prevents cryptic AttributeError later.
    - Asserts exactly 200 OK → bulk delete usually succeeds even on partial (no 207 Multi-Status)
    - Checks for expected response keys ("deleted" and "requested") → enforces the
      bulk metadata contract.
    - Returns only the parsed metadata dict → matches what most tests need
      (verify requested == len(ids), deleted count, sometimes check IDs no longer exist)

    This helper powers bulk_delete tests, cleanup after bulk_create, and scenarios
    where removing many items efficiently is needed.
    """
    resp = make_request(
        method="POST",
        url=f"{r['base']}/bulk/delete",
        json={"ids": ids}
    )
    assert resp is not None, (
        f"{r['label']} bulk delete completely failed — no response after retries.\n"
        f"POST {r['base']}/bulk/delete\n"
        f"payload ids count={len(ids)}"
    )
    assert resp.status_code == 200, (
        f"{r['label']} bulk delete failed.\n"
        f"POST {r['base']}/bulk/delete\n"
        f"status={resp.status_code}\n"
        f"body={resp.text[:1000]}"
    )
    data = resp.json()
    assert "deleted" in data and "requested" in data, (
        f"{r['label']} bulk delete response missing expected keys.\n"
        f"Got: {data}"
    )
    return data


# 10 follow-up questions & short answers

# 1. Why use POST instead of DELETE /bulk/delete with body?
#    → DELETE with body is non-standard and often blocked by proxies/CDNs/firewalls — POST is safer and widely accepted

# 2. Should we add assert data["requested"] == len(ids) for full request acknowledgment?
#    → Yes — strong check: add assert data["requested"] == len(ids), "Server did not acknowledge all IDs"

# 3. What if partial delete occurs (deleted < requested)?
#    → Test passes unless you add stricter assert data["deleted"] == len(ids) — partials are common in bulk ops

# 4. Why require exactly 200 OK instead of allowing 204 No Content or 207 Multi-Status?
#    → Bulk delete usually returns 200 with metadata; 204 would lack "deleted"/"requested" — can relax if backend varies

# 5. Should we check that len(data["deleted"]) == data["deleted"] (if deleted is list of IDs)?
#    → Good idea — add if isinstance(data["deleted"], list): assert len(data["deleted"]) == data["deleted"]

# 6. Can we follow up with GET /<id> on one deleted ID to confirm it's gone?
#    → Very strong — add: for one_id in ids[:1]: get_resp = _get_by_id(r["base"], one_id); assert get_resp.status_code == 404

# 7. Why truncate body to [:1000] in error message?
#    → Prevents pytest output from flooding with huge HTML error pages or logs

# 8. What if server returns 404 on bulk delete (resource not found)?
#    → Test fails — decide if 404 is acceptable (e.g. all IDs missing) or should be 200 + deleted=0

# 9. Should we allow empty ids list ([])? What does backend do?
#    → Current code sends [] → backend may 400 or 200 with requested=0; test can add case if needed

# 10. Should we return data["deleted"] list instead of metadata dict?
#     → No — metadata is usually enough; can return (data, data.get("deleted", [])) if tests need deleted IDs often

def _bulk_patch(r: Dict[str, Any], ids: List[int], changes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Purpose: Performs a bulk PATCH operation on multiple resources by sending
             a list of IDs and the fields/values to update in a single request.

    Why we do it this way:
    - Bulk patching is far more efficient than individual PATCH requests — fewer round-trips,
      often better transaction handling on the server side.
    - Uses PATCH to /bulk/patch with body containing {"ids": [...], "set": {...}} — matches
      the FastAPI route convention (@app.patch("/bulk/patch")) used in this backend.
    - Response is expected to contain metadata: "updated" (actual count of changed items)
      and "requested" (number of IDs sent) — allows verification that the operation succeeded
      fully or partially.
    - Uses make_request (httpx-based) instead of older wrappers → gains:
      - automatic retries on transient network issues (useful during local dev server restarts)
      - consistent 10-second timeout per attempt
      - verify=False (handles local self-signed certs or plain HTTP)
      - retry logging to console
      - Tkinter popup if the server is unreachable after all retry attempts
    - Explicit assert resp is not None protects against total network failure
      (all retries exhausted) — prevents cryptic AttributeError later.

    Returns: the parsed JSON response body (should contain "updated" and "requested" keys)

    Raises: AssertionError on failure (non-200 status, missing expected keys, no response)
    """
    payload = {"ids": ids, "set": changes}

    resp = make_request(
        method="PATCH",                      # ← Changed from "POST" to "PATCH"
        url=f"{r['base']}/bulk/patch",
        json=payload
    )

    assert resp is not None, (
        f"{r['label']} bulk patch completely failed — no response after retries.\n"
        f"PATCH {r['base']}/bulk/patch\n"   # ← Updated message for accuracy
        f"ids count={len(ids)}, changes={changes}"
    )

    assert resp.status_code == 200, (
        f"{r['label']} bulk patch failed.\n"
        f"PATCH {r['base']}/bulk/patch\n"   # ← Updated message
        f"status={resp.status_code}\n"
        f"body={resp.text[:1000]}"
    )

    data = resp.json()

    assert "updated" in data and "requested" in data, (
        f"{r['label']} bulk patch response missing expected keys.\n"
        f"Got: {data}"
    )

    return data


# 10 follow-up questions & short answers

# 1. Why use PATCH instead of POST even though the endpoint is named /bulk/patch ?
#    → Because the FastAPI route is decorated with @app.patch — POST returns 405 Method Not Allowed

# 2. Why does the payload use "set" as the key for changes instead of "changes" or "data"?
#    → Matches the backend Pydantic model / request body expectation — common naming in bulk-update APIs

# 3. Should we also assert that data["updated"] == len(ids) ?
#    → Yes — that's a stronger check (full success). Currently only checks presence of keys.

# 4. What happens if some IDs don't exist — does the backend still return 200?
#    → Depends on implementation. Many bulk endpoints return 200 + partial "updated" count.

# 5. Why allow changes to contain any dict — shouldn't we validate the allowed fields?
#    → Validation belongs in backend. Here we only care that the request is sent and response shape is correct.

# 6. Is there risk of partial updates (some succeed, some fail) without transaction?
#    → Possible — depends if backend wraps the bulk op in a DB transaction. Test can be extended to verify.

# 7. Why truncate body to [:1000] in error message?
#    → Prevents pytest output from becoming unreadable when server returns huge HTML error pages.

# 8. Should we retry on 500s or only on connection errors?
#    → Current make_request retries only on RequestError (connection/timeout). You could extend to retry on 5xx.

# 9. Can we make the method ("PATCH") configurable per resource?
#    → Yes — add r["bulk_patch_method"] = "PATCH" in the resource config dict if some resources differ.

# 10. Why return data instead of (resp, data) like some other helpers?
#     → Consistency with _bulk_create / _bulk_delete — they only return the parsed metadata dict.

# ----------------------------
# Build exactly 50 cases from discovered bases
# ----------------------------
EXTRA_ENDPOINTS = ["count", "ids", "exists", "search", "filter", "bulk_create", "bulk_delete", "bulk_patch"]

@pytest.fixture(scope="session")
def discovered_resources():
    swagger = _load_swagger()
    bases = _discover_bases(swagger)
    assert bases, "No bases discovered. Did you register /count endpoints with register_common_extras?"
    return [_make_resource(swagger, b) for b in bases]

def _build_cases(resources: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], str]]:
    cases: List[Tuple[Dict[str, Any], str]] = []
    for r in resources:
        for ep in EXTRA_ENDPOINTS:
            cases.append((r, ep))
    return cases[:50]


# ----------------------------
# Tests (50)
# ----------------------------
@pytest.mark.parametrize("idx", range(50))
def test_register_common_extras_50_cases(discovered_resources, idx):
    """
    Purpose:  One big parametrized test that verifies ~10 common "extra" endpoints
              (count, ids, exists, search, filter, bulk_create, bulk_delete, bulk_patch, ...)
              for up to 50 different resource types discovered in the API.

    Why we do it this way:
    - Instead of writing 8–12 separate tests × number of resources → we get high coverage
      with very little code duplication.
    - 50 cases = reasonable upper bound for most pet-store-like APIs (pets, orders, inventory, users, etc.)
    - Uses discovered_resources + _build_cases() to dynamically generate test cases → no hardcoding
      resource names/endpoints → easy to add new resources without touching this test.
    - Each case creates fresh data (via _create_one with seeded uuid) → strong isolation.
    - Covers both happy path + negative cases (missing params → 400).
    - Skips gracefully when a resource doesn't support a feature (missing search_key, etc.).
    - The single test body branches on 'ep' (endpoint type) → keeps related assertions together.
    - Updated to use make_request everywhere for retries, timeout, verify=False, and better failure visibility.
    - 50 cases are executed in a single test function → pytest shows them as separate runs with clear IDs
      (e.g. [0], [1], … [49]) → easy to rerun a single failing case with -k "idx==42"

    How it works:
    - _build_cases() returns a list of (r, ep) tuples from swagger discovery
    - For each idx we pull the config and run the matching branch
    - All HTTP calls now go through make_request → full robustness benefits

    This meta-test gives massive coverage with minimal maintenance.
    """
    r, ep = _build_cases(discovered_resources)[idx]
    seed_i = uuid.uuid4().int % 1_000_000
    created = _create_one(r, i=seed_i)
    if ep == "count":
        resp = make_request("GET", f"{r['base']}/count")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("count"), int)
        assert data["count"] >= 1
    elif ep == "ids":
        resp = make_request("GET", f"{r['base']}/ids")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("ids"), list)
        assert created["id"] in data["ids"]
    elif ep == "exists":
        resp = make_request("GET", f"{r['base']}/exists/{created['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("exists") is True
        assert data.get("id") == created["id"]
    elif ep == "search":
        q_val = created.get(r["search_key"])
        if q_val is None:
            pytest.skip(f"{r['label']} created item missing searchable key {r['search_key']}")
        resp = make_request("GET", f"{r['base']}/search", params={"q": str(q_val)})
        assert resp.status_code == 200, f"{r['label']} search failed: {resp.text}"
        items = resp.json()
        assert isinstance(items, list)
        assert any(x.get("id") == created["id"] for x in items)
        # Missing q should 400
        resp2 = make_request("GET", f"{r['base']}/search")
        assert resp2.status_code == 400
    elif ep == "filter":
        k = r["filter_key"]
        v = r["filter_val"]
        if v is None:
            pytest.skip(f"{r['label']} filter not configured in test mapping")
        # Ensure an item matches the filter
        if str(created.get(k)) != str(v):
            payload = r["make_payload"](seed_i + 1)
            payload[k] = v
            resp_seed = make_request("POST", r["create"], json=payload)
            assert resp_seed.status_code in (200, 201), f"{r['label']} filter seed failed: {resp_seed.text}"
            match = resp_seed.json()
        else:
            match = created
        resp = make_request("GET", f"{r['base']}/filter", params={k: v})
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert any(x.get("id") == match["id"] for x in items)
        # No params should 400
        resp2 = make_request("GET", f"{r['base']}/filter")
        assert resp2.status_code == 400
    elif ep == "bulk_create":
        objs = [r["make_payload"](seed_i + 10), r["make_payload"](seed_i + 11)]
        out = _bulk_create(r, objs) # already uses make_request internally
        assert out["count"] == 2
        assert all(isinstance(x.get("id"), int) for x in out["created"])
    elif ep == "bulk_delete":
        c1 = _create_one(r, i=seed_i + 20)
        c2 = _create_one(r, i=seed_i + 21)
        out = _bulk_delete(r, [c1["id"], c2["id"]]) # already uses make_request internally
        assert out["requested"] == 2
    elif ep == "bulk_patch":
        c1 = _create_one(r, i=seed_i + 30)
        c2 = _create_one(r, i=seed_i + 31)
        # safe patch field
        changes = {"name": f"{r['label']} Patched"}
        if "pet" in r["base"].lower():
            changes = {"status": "pending"}
        out = _bulk_patch(r, [c1["id"], c2["id"]], changes) # assuming _bulk_patch also uses make_request
        assert out["requested"] == 2
    else:
        raise AssertionError(f"Unknown ep: {ep}")


# 10 follow-up questions & short answers

# 1. Why 50 cases instead of exactly the number of resources × ep types?
#    → Caps runtime; 50 is a safe upper bound that still gives excellent coverage

# 2. Why seed_i = uuid.uuid4().int % 1_000_000 instead of full UUID?
#    → Produces smaller numbers that are easier to read in logs/DB while remaining collision-resistant

# 3. Why skip instead of fail when search_key or filter_val is missing?
#    → Some resources genuinely don't support search/filter → failing would be a false positive

# 4. Why create fresh data for every case even for read-only endpoints like /count?
#    → Guarantees isolation — no interference if previous case left dirty state

# 5. Why use make_request everywhere instead of the old _get / _post_json?
#    → Retries, timeout, verify=False, better error messages, and Tkinter popup on total failure

# 6. What if a resource has both /search and /filter but we only test one?
#    → Test only exercises the configured one — can extend _make_resource later for more

# 7. Why special-case "pet" for bulk_patch field?
#    → Pets often can't patch "name" freely or have different allowed fields → safe default

# 8. Why assert out["count"] == 2 in bulk_create but only out["requested"] == 2 in others?
#    → Bulk_create returns the actual created count; bulk_delete/patch return requested count

# 9. Can we split this into separate parametrized tests per ep type?
#    → Yes — would make failures easier to read but would lose the "one test per resource" grouping

# 10. What is the easiest way to run only one specific case (e.g. bulk_patch on pets)?
#     → pytest -k "idx==47 and pet" or pytest -k "idx==31" — idx is visible in test names