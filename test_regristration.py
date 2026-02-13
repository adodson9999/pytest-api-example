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


