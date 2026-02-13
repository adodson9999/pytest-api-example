from jsonschema.exceptions import ValidationError
import jsonschema
import pytest
import schemas
import api_helpers
from hamcrest import assert_that, contains_string, is_

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
    endpoint = f"{base_path}/{item_id}"
    response = api_helpers.make_request("GET", endpoint)

    assert response.status_code == 404, (
        f"Expected 404 for {label} id={item_id} at {endpoint}, got {response.status_code}. "
        f"Body: {response.text}"
    )

import pytest
import uuid
import api_helpers


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
    resp = api_helpers.make_request("GET", f"{base}/")
    return resp


def _create_item(base: str, payload: dict):
    return api_helpers.make_request("POST", f"{base}/", json=payload)


def _get_by_id(base: str, item_id):
    return api_helpers.make_request("GET", f"{base}/{item_id}")


# -----------------------------
# 1) LIST endpoint tests
#    7 resources * 4 tests = 28 tests
# -----------------------------
@pytest.mark.parametrize("r", RESOURCES)
def test_list_returns_200(r):
    resp = _list_all(r["base"])
    assert resp.status_code == 200, f"{r['label']} list should be 200. Body: {resp.text}"


@pytest.mark.parametrize("r", RESOURCES)
def test_list_returns_json(r):
    resp = _list_all(r["base"])
    assert "application/json" in resp.headers.get("Content-Type", "").lower(), (
        f"{r['label']} list should return JSON. Content-Type: {resp.headers.get('Content-Type')}"
    )


@pytest.mark.parametrize("r", RESOURCES)
def test_list_returns_list_type(r):
    resp = _list_all(r["base"])
    assert resp.status_code == 200, f"{r['label']} list should be 200. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, list), f"{r['label']} list should return a list, got {type(data)}"


@pytest.mark.parametrize("r", RESOURCES)
def test_list_items_are_dicts_if_present(r):
    resp = _list_all(r["base"])
    assert resp.status_code == 200, f"{r['label']} list should be 200. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert isinstance(data[0], dict), f"{r['label']} list items should be dicts, got {type(data[0])}"


# -----------------------------
# 2) GET BY ID 404 tests
#    7 resources * 3 invalid ids = 21 tests
# -----------------------------
@pytest.mark.parametrize("r", RESOURCES)
@pytest.mark.parametrize("item_id", INVALID_INT_IDS)
def test_get_by_id_404_for_invalid_ints(r, item_id):
    resp = _get_by_id(r["base"], item_id)
    assert resp.status_code == 404, (
        f"Expected 404 for {r['label']} id={item_id}, got {resp.status_code}. Body: {resp.text}"
    )


# Non-numeric path test (one per resource) = 7 tests
@pytest.mark.parametrize("r", RESOURCES)
def test_get_by_id_404_for_non_numeric(r):
    resp = _get_by_id(r["base"], NON_NUMERIC_ID)
    assert resp.status_code == 404, (
        f"Expected 404 for {r['label']} non-numeric id, got {resp.status_code}. Body: {resp.text}"
    )


# -----------------------------
# 3) POST behavior tests
#    7 resources * 4 tests = 28 tests
# -----------------------------
@pytest.mark.parametrize("r", RESOURCES)
def test_post_creates_201(r):
    payload = r["make_payload"]()
    resp = _create_item(r["base"], payload)
    assert resp.status_code in (200, 201), (
        f"{r['label']} create should return 201/200. Got {resp.status_code}. Body: {resp.text}"
    )


@pytest.mark.parametrize("r", RESOURCES)
def test_post_returns_json_object(r):
    payload = r["make_payload"]()
    resp = _create_item(r["base"], payload)
    assert resp.status_code in (200, 201), f"{r['label']} create failed. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, dict), f"{r['label']} create should return dict, got {type(data)}"


@pytest.mark.parametrize("r", RESOURCES)
def test_post_server_generates_id_if_missing(r):
    payload = r["make_payload"]()
    payload.pop("id", None)  # ensure missing
    resp = _create_item(r["base"], payload)
    assert resp.status_code in (200, 201), f"{r['label']} create failed. Body: {resp.text}"
    data = resp.json()
    assert "id" in data, f"{r['label']} server should generate id. Response: {data}"
    assert isinstance(data["id"], int), f"{r['label']} id should be int. Got: {data['id']}"


@pytest.mark.parametrize("r", RESOURCES)
def test_post_rejects_non_int_id_400(r):
    payload = r["make_payload"]()
    payload["id"] = "not-an-int"
    resp = _create_item(r["base"], payload)
    assert resp.status_code == 400, (
        f"{r['label']} should reject non-int id with 400. Got {resp.status_code}. Body: {resp.text}"
    )


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



import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pytest
import requests


# ----------------------------
# Config: point this at your running API
# ----------------------------
BASE_URL = "http://localhost:5001"

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

import uuid
from typing import Any, Dict, List, Optional, Tuple

import pytest
import requests


BASE_URL = "http://localhost:5001"


# ----------------------------
# HTTP helpers
# ----------------------------
def _url(path: str) -> str:
    return f"{BASE_URL}{path}"

def _get(path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    return requests.get(_url(path), params=params)

def _post_json(path: str, body: Any) -> requests.Response:
    return requests.post(_url(path), json=body, headers={"Content-Type": "application/json"})

def _patch_json(path: str, body: Any) -> requests.Response:
    return requests.patch(_url(path), json=body, headers={"Content-Type": "application/json"})


# ----------------------------
# Swagger discovery
# ----------------------------
def _load_swagger() -> Dict[str, Any]:
    # Try common swagger.json locations
    for p in ("/swagger.json", "/api/swagger.json", "/v1/swagger.json", "/api/v1/swagger.json"):
        r = _get(p)
        if r.status_code == 200:
            return r.json()
    raise AssertionError(
        "Could not find swagger.json at common paths. "
        "Try opening /swagger.json in browser to see where it is."
    )

def _discover_bases(swagger: Dict[str, Any]) -> List[str]:
    """
    Discover base resources that have the register_common_extras endpoints.
    We look for paths ending with /count and infer the base.
    """
    paths = swagger.get("paths", {})
    bases = set()

    for path in paths.keys():
        # Example: /pet/count -> base /pet
        if path.endswith("/count"):
            base = path[: -len("/count")]
            bases.add(base)

    return sorted(bases)

def _pick_create_path(swagger: Dict[str, Any], base: str) -> str:
    """
    Your create endpoint might be:
      POST {base}/
    or POST {base}
    We'll try both, based on swagger paths.
    """
    paths = swagger.get("paths", {})
    if base in paths and "post" in paths[base]:
        return base
    if f"{base}/" in paths and "post" in paths[f"{base}/"]:
        return f"{base}/"
    # fallback to base + "/"
    return f"{base}/"


# ----------------------------
# Generic payload maker (minimal valid objects)
# You can override per base if needed.
# ----------------------------
def _default_payload_for_base(base: str, i: int) -> Dict[str, Any]:
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


# ----------------------------
# Test resource wrapper discovered from swagger
# ----------------------------
def _make_resource(swagger: Dict[str, Any], base: str) -> Dict[str, Any]:
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


# ----------------------------
# Shared helpers for the tests
# ----------------------------
def _create_one(r: Dict[str, Any], *, i: int) -> Dict[str, Any]:
    payload = r["make_payload"](i)
    resp = _post_json(r["create"], payload)
    assert resp.status_code in (200, 201), (
        f"{r['label']} create failed.\n"
        f"POST {r['create']}\n"
        f"status={resp.status_code}\n"
        f"body={resp.text[:1000]}"
    )
    data = resp.json()
    assert isinstance(data.get("id"), int), f"{r['label']} create missing/invalid id. Body: {data}"
    return data

def _bulk_create(r: Dict[str, Any], objs: List[Dict[str, Any]]) -> Dict[str, Any]:
    resp = _post_json(f"{r['base']}/bulk", objs)
    assert resp.status_code in (200, 201), f"{r['label']} bulk create failed. {resp.status_code} Body: {resp.text}"
    data = resp.json()
    assert "created" in data and "count" in data
    return data

def _bulk_delete(r: Dict[str, Any], ids: List[int]) -> Dict[str, Any]:
    resp = _post_json(f"{r['base']}/bulk/delete", {"ids": ids})
    assert resp.status_code == 200, f"{r['label']} bulk delete failed. {resp.status_code} Body: {resp.text}"
    data = resp.json()
    assert "deleted" in data and "requested" in data
    return data

def _bulk_patch(r: Dict[str, Any], ids: List[int], changes: Dict[str, Any]) -> Dict[str, Any]:
    resp = _patch_json(f"{r['base']}/bulk/patch", {"ids": ids, "set": changes})
    assert resp.status_code == 200, f"{r['label']} bulk patch failed. {resp.status_code} Body: {resp.text}"
    data = resp.json()
    assert "updated" in data and "requested" in data
    return data


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
    r, ep = _build_cases(discovered_resources)[idx]

    seed_i = uuid.uuid4().int % 1_000_000
    created = _create_one(r, i=seed_i)

    if ep == "count":
        resp = _get(f"{r['base']}/count")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("count"), int)
        assert data["count"] >= 1

    elif ep == "ids":
        resp = _get(f"{r['base']}/ids")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("ids"), list)
        assert created["id"] in data["ids"]

    elif ep == "exists":
        resp = _get(f"{r['base']}/exists/{created['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("exists") is True
        assert data.get("id") == created["id"]

    elif ep == "search":
        q_val = created.get(r["search_key"])
        if q_val is None:
            pytest.skip(f"{r['label']} created item missing searchable key {r['search_key']}")
        resp = _get(f"{r['base']}/search", params={"q": str(q_val)})
        assert resp.status_code == 200, f"{r['label']} search failed: {resp.text}"
        items = resp.json()
        assert isinstance(items, list)
        assert any(x.get("id") == created["id"] for x in items)

        # Missing q should 400
        resp2 = _get(f"{r['base']}/search")
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
            resp_seed = _post_json(r["create"], payload)
            assert resp_seed.status_code in (200, 201), f"{r['label']} filter seed failed: {resp_seed.text}"
            match = resp_seed.json()
        else:
            match = created

        resp = _get(f"{r['base']}/filter", params={k: v})
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert any(x.get("id") == match["id"] for x in items)

        # No params should 400
        resp2 = _get(f"{r['base']}/filter")
        assert resp2.status_code == 400

    elif ep == "bulk_create":
        objs = [r["make_payload"](seed_i + 10), r["make_payload"](seed_i + 11)]
        out = _bulk_create(r, objs)
        assert out["count"] == 2
        assert all(isinstance(x.get("id"), int) for x in out["created"])

    elif ep == "bulk_delete":
        c1 = _create_one(r, i=seed_i + 20)
        c2 = _create_one(r, i=seed_i + 21)
        out = _bulk_delete(r, [c1["id"], c2["id"]])
        assert out["requested"] == 2

    elif ep == "bulk_patch":
        c1 = _create_one(r, i=seed_i + 30)
        c2 = _create_one(r, i=seed_i + 31)

        # safe patch field
        changes = {"name": f"{r['label']} Patched"}
        if "pet" in r["base"].lower():
            changes = {"status": "pending"}

        out = _bulk_patch(r, [c1["id"], c2["id"]], changes)
        assert out["requested"] == 2

    else:
        raise AssertionError(f"Unknown ep: {ep}")
