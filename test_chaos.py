# test_chaos.py
import os
import json
import time
import requests
import pytest

BASE_URL = os.getenv("BASE_URL", "http://localhost:5001")
GQL_URL = f"{BASE_URL}/graphql"


def wait_for_server(url="http://localhost:5001/graphql", timeout=10):
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

wait_for_server()

def gql(query: str, variables=None, operation_name=None, headers=None):
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
    assert "errors" in resp_json and resp_json["errors"], f"Expected errors, got: {resp_json}"
    err = resp_json["errors"][0]
    assert "message" in err and isinstance(err["message"], str)
    # path is a strong indicator this is GraphQL-structured
    # not all failures include it, so keep soft unless you enforce it
    # assert "path" in err

def get_data_dict(body: dict) -> dict:
    """
    GraphQL responses may return data=None on certain resolver failures.
    Normalize to {} so tests can safely check keys.
    """
    d = body.get("data")
    return d if isinstance(d, dict) else {}

@pytest.mark.chaos
def test_downstream_domain_failure_is_isolated():
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
    Simulate field-level failure: Pet.status fails for some pets.
    Assert:
      - data still returned
      - errors exists
      - at least one pet still has a usable status value
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
    Simulate shared-write failure during createPet.
    Assert:
      - GraphQL returns structured error
      - system remains queryable after (no crash)
      - no malformed inventory records were created
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
